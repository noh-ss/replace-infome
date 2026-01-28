"""
URL 관리자
URL 큐 관리, 중복 제거, 도메인 필터링
"""

import hashlib
import sqlite3
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin
import fnmatch

from config.settings import settings
from src.utils.logger import get_crawler_logger


logger = get_crawler_logger()


class URLManager:
    """URL 큐 및 상태 관리"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        URLManager 초기화

        Args:
            db_path: SQLite 데이터베이스 파일 경로
        """
        self.db_path = db_path or (settings.metadata_dir / "crawl_metadata.db")
        self.allowed_domains = set(settings.get_allowed_domains())
        self.exclude_patterns = settings.get_exclude_patterns()

        # 메모리 캐시 (성능 향상)
        self.visited_urls: Set[str] = set()
        self.pending_urls: List[tuple] = []  # [(url, depth), ...]

        # 데이터베이스 초기화
        self._init_database()
        self._load_from_database()

        logger.info(f"URL Manager initialized. DB: {self.db_path}")

    def _init_database(self):
        """데이터베이스 테이블 생성"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # URLs 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                url TEXT PRIMARY KEY,
                url_hash TEXT UNIQUE,
                status TEXT,  -- pending, visited, failed
                depth INTEGER,
                crawl_date TEXT,
                error_message TEXT
            )
        """)

        # 크롤링 세션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_sessions (
                session_id TEXT PRIMARY KEY,
                start_time TEXT,
                end_time TEXT,
                pages_crawled INTEGER,
                pages_failed INTEGER
            )
        """)

        # URL 추출 내역 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                extracted_at TEXT NOT NULL,
                total_links INTEGER,
                filtered_links INTEGER,
                added_to_queue INTEGER,
                status TEXT DEFAULT 'completed'
            )
        """)

        # 추출된 링크 상세 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extracted_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                extraction_id INTEGER,
                link_url TEXT NOT NULL,
                added_to_queue INTEGER DEFAULT 0,
                FOREIGN KEY (extraction_id) REFERENCES extraction_history(id)
            )
        """)

        conn.commit()
        conn.close()

    def _load_from_database(self):
        """데이터베이스에서 기존 URL 로드"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 방문한 URL 로드
        cursor.execute("SELECT url FROM urls WHERE status = 'visited'")
        self.visited_urls = {row[0] for row in cursor.fetchall()}

        # 대기 중인 URL 로드
        cursor.execute("SELECT url, depth FROM urls WHERE status = 'pending' ORDER BY depth")
        self.pending_urls = list(cursor.fetchall())

        conn.close()

        logger.info(f"Loaded {len(self.visited_urls)} visited URLs and {len(self.pending_urls)} pending URLs")

    def add_url(self, url: str, depth: int = 0) -> bool:
        """
        URL을 큐에 추가

        Args:
            url: 추가할 URL
            depth: 크롤링 깊이

        Returns:
            추가 성공 여부
        """
        # URL 정규화
        url = self._normalize_url(url)

        # 필터링 검사
        if not self._is_valid_url(url):
            return False

        # 중복 검사
        if url in self.visited_urls or any(u[0] == url for u in self.pending_urls):
            return False

        # 깊이 제한 검사
        if depth > settings.crawl.max_crawl_depth:
            logger.debug(f"Skipping URL (max depth exceeded): {url}")
            return False

        # 메모리 캐시에 추가
        self.pending_urls.append((url, depth))

        # 데이터베이스에 추가
        url_hash = self._hash_url(url)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO urls (url, url_hash, status, depth)
                VALUES (?, ?, 'pending', ?)
            """, (url, url_hash, depth))
            conn.commit()
            logger.debug(f"Added URL to queue (depth={depth}): {url}")
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def add_urls(self, urls: List[str], depth: int = 0) -> int:
        """
        여러 URL을 큐에 추가

        Args:
            urls: URL 목록
            depth: 크롤링 깊이

        Returns:
            추가된 URL 개수
        """
        added_count = 0
        for url in urls:
            if self.add_url(url, depth):
                added_count += 1
        return added_count

    def get_next_url(self) -> Optional[tuple]:
        """
        다음 크롤링할 URL 가져오기

        Returns:
            (url, depth) 튜플 또는 None
        """
        if not self.pending_urls:
            return None

        return self.pending_urls.pop(0)

    def mark_visited(self, url: str, success: bool = True, error_message: str = None):
        """
        URL을 방문 완료로 표시

        Args:
            url: 방문한 URL
            success: 성공 여부
            error_message: 에러 메시지 (실패 시)
        """
        url = self._normalize_url(url)
        self.visited_urls.add(url)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        status = 'visited' if success else 'failed'

        cursor.execute("""
            UPDATE urls
            SET status = ?, crawl_date = datetime('now'), error_message = ?
            WHERE url = ?
        """, (status, error_message, url))

        conn.commit()
        conn.close()

        if success:
            logger.info(f"Marked as visited: {url}")
        else:
            logger.warning(f"Marked as failed: {url} - {error_message}")

    def is_visited(self, url: str) -> bool:
        """URL 방문 여부 확인"""
        url = self._normalize_url(url)
        return url in self.visited_urls

    def get_queue_size(self) -> int:
        """대기 중인 URL 개수 반환"""
        return len(self.pending_urls)

    def get_visited_count(self) -> int:
        """방문한 URL 개수 반환"""
        return len(self.visited_urls)

    def _normalize_url(self, url: str) -> str:
        """URL 정규화 (프래그먼트 제거, 소문자 변환 등)"""
        parsed = urlparse(url)
        # 프래그먼트(#) 제거
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized

    def _hash_url(self, url: str) -> str:
        """URL을 해시값으로 변환"""
        return hashlib.sha256(url.encode()).hexdigest()

    def _is_valid_url(self, url: str) -> bool:
        """
        URL 유효성 검사

        - 허용된 도메인인지
        - 제외 패턴에 해당하지 않는지
        """
        parsed = urlparse(url)

        # 도메인 검사
        domain = parsed.netloc
        if self.allowed_domains and not any(
            domain == allowed or domain.endswith(f".{allowed}")
            for allowed in self.allowed_domains
        ):
            logger.debug(f"Skipping URL (domain not allowed): {url}")
            return False

        # 제외 패턴 검사
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(url, pattern):
                logger.debug(f"Skipping URL (matches exclude pattern '{pattern}'): {url}")
                return False

        return True

    def extract_links(self, base_url: str, html_links: List[str], current_depth: int) -> int:
        """
        HTML에서 추출한 링크들을 큐에 추가

        Args:
            base_url: 기준 URL
            html_links: 추출된 링크 목록
            current_depth: 현재 깊이

        Returns:
            추가된 링크 개수
        """
        added_count = 0

        for link in html_links:
            # 상대 URL을 절대 URL로 변환
            absolute_url = urljoin(base_url, link)

            # 큐에 추가 (깊이 +1)
            if self.add_url(absolute_url, current_depth + 1):
                added_count += 1

        logger.info(f"Extracted {added_count} new URLs from {base_url}")
        return added_count

    def get_stats(self) -> dict:
        """크롤링 통계 반환"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT status, COUNT(*) FROM urls GROUP BY status")
        status_counts = dict(cursor.fetchall())

        conn.close()

        return {
            "pending": self.get_queue_size(),
            "visited": self.get_visited_count(),
            "failed": status_counts.get("failed", 0),
            "total": sum(status_counts.values()),
        }


if __name__ == "__main__":
    # URLManager 테스트
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    manager = URLManager()

    # 시작 URL 추가
    start_urls = settings.get_crawl_start_urls()
    for url in start_urls:
        manager.add_url(url, depth=0)

    # 테스트 URL 추가
    test_urls = [
        "https://gnu.ac.kr/about/intro.do",
        "https://gnu.ac.kr/admission/info.do",
        "https://gnu.ac.kr/community/notice.do",
        "https://example.com/test",  # 허용되지 않은 도메인
        "https://gnu.ac.kr/file.pdf",  # 제외 패턴
    ]

    for url in test_urls:
        manager.add_url(url, depth=1)

    # 통계 출력
    stats = manager.get_stats()
    print("\n=== URL Manager Stats ===")
    print(f"Pending: {stats['pending']}")
    print(f"Visited: {stats['visited']}")
    print(f"Failed: {stats['failed']}")
    print(f"Total: {stats['total']}")

    # 다음 URL 가져오기
    print("\n=== Next URLs ===")
    for i in range(min(5, manager.get_queue_size())):
        next_url = manager.get_next_url()
        if next_url:
            print(f"{i+1}. {next_url[0]} (depth={next_url[1]})")

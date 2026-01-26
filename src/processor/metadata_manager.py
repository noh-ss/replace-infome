"""
메타데이터 관리자
청크에 메타데이터를 첨부하고 관리
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from src.utils.logger import get_processor_logger


logger = get_processor_logger()


class MetadataManager:
    """청크 메타데이터 관리"""

    def __init__(self):
        """MetadataManager 초기화"""
        logger.info("MetadataManager initialized")

    def create_chunk_metadata(
        self,
        text: str,
        url: str,
        title: str,
        chunk_index: int,
        total_chunks: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        청크 메타데이터 생성

        Args:
            text: 청크 텍스트
            url: 출처 URL
            title: 페이지 제목
            chunk_index: 청크 인덱스 (0부터 시작)
            total_chunks: 전체 청크 수
            metadata: 추가 메타데이터

        Returns:
            메타데이터가 포함된 청크 딕셔너리
        """
        # 고유 ID 생성
        chunk_id = self._generate_chunk_id(url, chunk_index)

        # 기본 메타데이터
        chunk_data = {
            "id": chunk_id,
            "text": text,
            "metadata": {
                "source_url": url,
                "title": title,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "char_count": len(text),
                "word_count": len(text.split()),
                "created_at": datetime.now().isoformat(),
                "domain": self._extract_domain(url),
                "url_path": self._extract_url_path(url),
            }
        }

        # 추가 메타데이터 병합
        if metadata:
            chunk_data["metadata"].update(metadata)

        return chunk_data

    def _generate_chunk_id(self, url: str, chunk_index: int) -> str:
        """
        청크 고유 ID 생성

        Args:
            url: 출처 URL
            chunk_index: 청크 인덱스

        Returns:
            고유 ID
        """
        # URL + 인덱스 기반 결정론적 ID
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        chunk_id = f"{url_hash}_{chunk_index:04d}"

        return chunk_id

    def _extract_domain(self, url: str) -> str:
        """
        URL에서 도메인 추출

        Args:
            url: URL

        Returns:
            도메인
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return "unknown"

    def _extract_url_path(self, url: str) -> str:
        """
        URL에서 경로 추출

        Args:
            url: URL

        Returns:
            경로
        """
        try:
            parsed = urlparse(url)
            return parsed.path
        except Exception:
            return "/"

    def enrich_metadata(
        self,
        chunk_data: Dict[str, Any],
        additional_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        기존 청크 데이터에 메타데이터 추가

        Args:
            chunk_data: 청크 데이터
            additional_data: 추가할 메타데이터

        Returns:
            업데이트된 청크 데이터
        """
        if "metadata" not in chunk_data:
            chunk_data["metadata"] = {}

        chunk_data["metadata"].update(additional_data)
        return chunk_data

    def extract_category_from_url(self, url: str) -> str:
        """
        URL에서 카테고리 추출

        Args:
            url: URL

        Returns:
            카테고리 (예: "admission", "library", "scholarship")
        """
        try:
            parsed = urlparse(url)
            path_parts = [p for p in parsed.path.split('/') if p]

            if not path_parts:
                return "home"

            # 첫 번째 경로 세그먼트를 카테고리로 사용
            category = path_parts[0]

            # 카테고리 매핑 (한글 -> 영어)
            category_map = {
                "admission": "입학",
                "academics": "학사",
                "research": "연구",
                "campus": "캠퍼스",
                "library": "도서관",
                "scholarship": "장학",
                "international": "국제",
                "employment": "취업",
                "notice": "공지",
                "bulletin": "게시판",
            }

            # 역방향 매핑 확인
            for eng, kor in category_map.items():
                if kor in category or eng in category:
                    return eng

            return category

        except Exception:
            return "general"

    def add_page_type(self, chunk_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        페이지 타입 추가 (일반 페이지 vs 게시판)

        Args:
            chunk_data: 청크 데이터
            url: URL

        Returns:
            업데이트된 청크 데이터
        """
        # URL 패턴으로 페이지 타입 판단
        page_type = "general"

        board_keywords = ["board", "bbs", "notice", "bulletin", "community", "forum"]
        for keyword in board_keywords:
            if keyword in url.lower():
                page_type = "bulletin"
                break

        chunk_data["metadata"]["page_type"] = page_type
        chunk_data["metadata"]["category"] = self.extract_category_from_url(url)

        return chunk_data

    def validate_chunk_data(self, chunk_data: Dict[str, Any]) -> bool:
        """
        청크 데이터 유효성 검증

        Args:
            chunk_data: 검증할 청크 데이터

        Returns:
            유효 여부
        """
        # 필수 필드 확인
        required_fields = ["id", "text", "metadata"]
        for field in required_fields:
            if field not in chunk_data:
                logger.error(f"Missing required field: {field}")
                return False

        # 메타데이터 필수 필드
        required_metadata = ["source_url", "title", "chunk_index"]
        metadata = chunk_data.get("metadata", {})

        for field in required_metadata:
            if field not in metadata:
                logger.error(f"Missing required metadata field: {field}")
                return False

        # 텍스트 길이 확인
        text = chunk_data.get("text", "")
        if len(text) < 10:
            logger.error(f"Text too short: {len(text)} characters")
            return False

        return True

    def get_chunk_summary(self, chunk_data: Dict[str, Any]) -> str:
        """
        청크 요약 정보 생성

        Args:
            chunk_data: 청크 데이터

        Returns:
            요약 문자열
        """
        metadata = chunk_data.get("metadata", {})

        summary = (
            f"ID: {chunk_data.get('id', 'N/A')}\n"
            f"Title: {metadata.get('title', 'N/A')}\n"
            f"Source: {metadata.get('source_url', 'N/A')}\n"
            f"Chunk: {metadata.get('chunk_index', 0) + 1}/{metadata.get('total_chunks', 1)}\n"
            f"Length: {metadata.get('char_count', 0)} chars, {metadata.get('word_count', 0)} words\n"
            f"Category: {metadata.get('category', 'N/A')}\n"
            f"Page Type: {metadata.get('page_type', 'N/A')}\n"
        )

        return summary


if __name__ == "__main__":
    # MetadataManager 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    manager = MetadataManager()

    # 테스트 데이터
    test_url = "https://gnu.ac.kr/admission/undergraduate/2024"
    test_title = "2024학년도 학부 신입생 모집요강"
    test_text = "경상국립대학교 2024학년도 학부 신입생 모집요강입니다. " * 10

    print("=== 청크 메타데이터 생성 ===\n")

    # 청크 생성
    chunk_data = manager.create_chunk_metadata(
        text=test_text,
        url=test_url,
        title=test_title,
        chunk_index=0,
        total_chunks=5,
        metadata={"author": "입학처", "date": "2024-01-15"}
    )

    # 페이지 타입 추가
    chunk_data = manager.add_page_type(chunk_data, test_url)

    print("생성된 청크 데이터:")
    print(f"ID: {chunk_data['id']}")
    print(f"Text (처음 100자): {chunk_data['text'][:100]}...")
    print("\nMetadata:")
    for key, value in chunk_data['metadata'].items():
        print(f"  {key}: {value}")

    print("\n=== 청크 요약 ===\n")
    summary = manager.get_chunk_summary(chunk_data)
    print(summary)

    print("=== 유효성 검증 ===\n")
    is_valid = manager.validate_chunk_data(chunk_data)
    print(f"유효성: {is_valid}")

    print("\n=== 카테고리 추출 테스트 ===\n")
    test_urls = [
        "https://gnu.ac.kr/admission/undergraduate",
        "https://gnu.ac.kr/library/info",
        "https://gnu.ac.kr/board/notice/123",
        "https://gnu.ac.kr/scholarship/apply",
    ]

    for url in test_urls:
        category = manager.extract_category_from_url(url)
        print(f"{url} -> {category}")

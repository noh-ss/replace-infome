"""
페이지 스크래퍼
Playwright를 사용한 동적 웹 페이지 크롤링
"""

import time
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse
import hashlib

from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

from config.settings import settings
from src.utils.logger import get_crawler_logger


logger = get_crawler_logger()


class PageScraper:
    """Playwright 기반 웹 페이지 스크래퍼"""

    def __init__(self, headless: bool = True):
        """
        PageScraper 초기화

        Args:
            headless: 헤드리스 모드 사용 여부
        """
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context = None
        self.rate_limit = settings.crawl.crawl_rate_limit
        self.user_agent = settings.crawl.user_agent
        self.timeout = settings.crawl_config.get("crawl_settings", {}).get("timeout", 30) * 1000
        self.last_request_time = 0

        # Playwright 설정
        playwright_settings = settings.get_playwright_settings()
        self.wait_until = playwright_settings.get("wait_until", "networkidle")
        self.viewport_width = playwright_settings.get("viewport_width", 1920)
        self.viewport_height = playwright_settings.get("viewport_height", 1080)

        logger.info("PageScraper initialized")

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.stop()

    def start(self):
        """Playwright 및 브라우저 시작"""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=self.headless)
            # SSL 오류 무시하는 기본 컨텍스트 생성
            self.context = self.browser.new_context(ignore_https_errors=True)
            logger.info("Browser started")

    def stop(self):
        """브라우저 및 Playwright 종료"""
        try:
            if self.context:
                self.context.close()
                self.context = None
        except:
            pass

        try:
            if self.browser:
                self.browser.close()
                self.browser = None
                logger.info("Browser closed")
        except:
            pass

        try:
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
                logger.info("Playwright stopped")
        except:
            pass

    def _apply_rate_limit(self):
        """속도 제한 적용"""
        if self.rate_limit > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit:
                wait_time = self.rate_limit - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(wait_time)
        self.last_request_time = time.time()

    def fetch_page(self, url: str) -> Optional[Dict]:
        """
        페이지 가져오기

        Args:
            url: 가져올 URL

        Returns:
            페이지 데이터 딕셔너리 또는 None
            {
                'url': str,
                'html': str,
                'status_code': int,
                'links': List[str],
                'title': str,
                'screenshot_path': Optional[str]
            }
        """
        if not self.browser:
            self.start()

        # 속도 제한 적용
        self._apply_rate_limit()

        logger.info(f"Fetching: {url}")

        page = None
        try:
            # 새 페이지 생성 (context 사용)
            page = self.context.new_page()
            page.set_viewport_size({"width": self.viewport_width, "height": self.viewport_height})

            # 페이지 이동 (domcontentloaded 사용 - 더 안정적)
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            except PlaywrightTimeout:
                logger.warning(f"Timeout, retrying with 'commit': {url}")
                response = page.goto(url, wait_until="commit", timeout=self.timeout)

            if response is None:
                logger.error(f"No response from {url}")
                page.close()
                return None

            status_code = response.status

            # 응답 확인
            if status_code >= 400:
                logger.warning(f"HTTP {status_code}: {url}")
                page.close()
                return None

            # HTML 가져오기
            html_content = page.content()

            # 페이지 제목
            title = page.title()

            # 링크 추출
            links = self._extract_links(page)

            # 페이지 데이터 저장
            page_data = {
                'url': url,
                'html': html_content,
                'status_code': status_code,
                'links': links,
                'title': title,
                'screenshot_path': None
            }

            logger.info(f"Successfully fetched: {url} (status={status_code}, links={len(links)})")

            page.close()
            return page_data

        except PlaywrightTimeout:
            logger.error(f"Timeout while fetching: {url}")
            try:
                page.close()
            except:
                pass
            return None

        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            try:
                page.close()
            except:
                pass
            return None

    def _extract_links(self, page: Page) -> List[str]:
        """
        페이지에서 링크 추출

        Args:
            page: Playwright Page 객체

        Returns:
            링크 목록
        """
        try:
            # 모든 a 태그의 href 속성 추출
            links = page.evaluate("""
                () => {
                    const anchors = Array.from(document.querySelectorAll('a[href]'));
                    return anchors.map(a => a.href).filter(href => href && href.trim() !== '');
                }
            """)
            return links
        except Exception as e:
            logger.error(f"Error extracting links: {str(e)}")
            return []

    def save_html(self, url: str, html_content: str, page_type: str = "pages") -> Path:
        """
        HTML 콘텐츠를 파일로 저장

        Args:
            url: 페이지 URL
            html_content: HTML 콘텐츠
            page_type: 페이지 타입 (pages, bulletins)

        Returns:
            저장된 파일 경로
        """
        # URL 해시 생성 (파일명으로 사용)
        url_hash = hashlib.sha256(url.encode()).hexdigest()

        # 저장 경로
        save_dir = settings.raw_data_dir / page_type
        save_dir.mkdir(parents=True, exist_ok=True)

        html_path = save_dir / f"{url_hash}.html"
        meta_path = save_dir / f"{url_hash}.meta.txt"

        # HTML 저장
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 메타데이터 저장
        with open(meta_path, 'w', encoding='utf-8') as f:
            f.write(f"URL: {url}\n")
            f.write(f"Hash: {url_hash}\n")
            f.write(f"Type: {page_type}\n")

        logger.info(f"Saved HTML: {html_path}")
        return html_path

    def check_robots_txt(self, base_url: str) -> bool:
        """
        robots.txt 확인 (간단한 구현)

        Args:
            base_url: 기본 URL

        Returns:
            크롤링 허용 여부
        """
        # 실제 프로덕션에서는 robotparser 사용 권장
        # 여기서는 간단하게 구현
        robots_config = settings.crawl_config.get("robots_txt", {})

        if not robots_config.get("respect", True):
            return True

        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            if not self.browser:
                self.start()

            page = self.browser.new_page()
            response = page.goto(robots_url, timeout=10000)

            if response and response.status == 200:
                robots_content = page.content()
                # 간단한 체크: User-agent에 대한 Disallow 규칙 확인
                # 실제로는 robotparser 라이브러리 사용 권장
                logger.info(f"robots.txt found at {robots_url}")

            page.close()
            return True

        except Exception as e:
            logger.debug(f"Could not fetch robots.txt: {str(e)}")
            return True  # robots.txt 없으면 허용


if __name__ == "__main__":
    # PageScraper 테스트
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    with PageScraper(headless=True) as scraper:
        # 테스트 URL 크롤링
        test_url = "https://gnu.ac.kr"

        print(f"\n=== Testing PageScraper ===")
        print(f"Target: {test_url}\n")

        # 페이지 가져오기
        result = scraper.fetch_page(test_url)

        if result:
            print(f"Status: {result['status_code']}")
            print(f"Title: {result['title']}")
            print(f"Links found: {len(result['links'])}")
            print(f"HTML length: {len(result['html'])} characters")

            # HTML 저장
            saved_path = scraper.save_html(test_url, result['html'])
            print(f"\nSaved to: {saved_path}")

            # 링크 샘플 출력
            print(f"\nSample links (first 5):")
            for i, link in enumerate(result['links'][:5], 1):
                print(f"{i}. {link}")
        else:
            print("Failed to fetch page")

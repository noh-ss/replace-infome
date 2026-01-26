"""
콘텐츠 추출기
HTML에서 주요 콘텐츠 추출
"""

from typing import Dict, Optional
from bs4 import BeautifulSoup

from src.utils.logger import get_crawler_logger


logger = get_crawler_logger()


class ContentExtractor:
    """HTML 콘텐츠 추출기"""

    def __init__(self):
        """ContentExtractor 초기화"""
        logger.info("ContentExtractor initialized")

    def extract(self, html: str, url: str) -> Dict:
        """
        HTML에서 콘텐츠 추출

        Args:
            html: HTML 콘텐츠
            url: 페이지 URL

        Returns:
            추출된 콘텐츠 딕셔너리
            {
                'title': str,
                'content': str,
                'metadata': dict
            }
        """
        soup = BeautifulSoup(html, 'lxml')

        # 제목 추출
        title = self._extract_title(soup)

        # 메타데이터 추출
        metadata = self._extract_metadata(soup, url)

        # 주요 콘텐츠 추출
        content = self._extract_main_content(soup)

        logger.info(f"Extracted content from {url}: {len(content)} characters")

        return {
            'title': title,
            'content': content,
            'metadata': metadata
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """페이지 제목 추출"""
        # title 태그
        if soup.title:
            return soup.title.get_text(strip=True)

        # h1 태그
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        return ""

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """메타데이터 추출"""
        metadata = {'url': url}

        # 메타 태그
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description:
            metadata['description'] = meta_description.get('content', '')

        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            metadata['keywords'] = meta_keywords.get('content', '')

        # OG 태그
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['og_title'] = og_title.get('content', '')

        return metadata

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        주요 콘텐츠 추출

        불필요한 요소(nav, footer, script, style 등) 제거
        """
        # 제거할 태그들
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # 주요 콘텐츠 영역 찾기
        main_content = None

        # 일반적인 콘텐츠 영역 선택자
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '#content',
            '.content',
            '#main',
            '.main',
            'body'
        ]

        for selector in content_selectors:
            if selector.startswith('#') or selector.startswith('.') or selector.startswith('['):
                main_content = soup.select_one(selector)
            else:
                main_content = soup.find(selector)

            if main_content:
                break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # 텍스트 추출
        text = main_content.get_text(separator='\n', strip=True)

        # 공백 정리
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned_text = '\n'.join(lines)

        return cleaned_text


if __name__ == "__main__":
    # ContentExtractor 테스트
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    extractor = ContentExtractor()

    # 테스트 HTML
    test_html = """
    <html>
    <head>
        <title>경상국립대학교 - 대학 소개</title>
        <meta name="description" content="경상국립대학교에 오신 것을 환영합니다">
    </head>
    <body>
        <nav>메뉴1 메뉴2 메뉴3</nav>
        <header>헤더 내용</header>
        <main>
            <h1>대학 소개</h1>
            <article>
                <p>경상국립대학교는 1948년에 설립된 국립대학교입니다.</p>
                <p>우리 대학은 교육, 연구, 봉사를 통해 지역사회와 국가 발전에 기여하고 있습니다.</p>
            </article>
        </main>
        <footer>푸터 내용</footer>
        <script>console.log('test');</script>
    </body>
    </html>
    """

    result = extractor.extract(test_html, "https://gnu.ac.kr/test")

    print("\n=== Content Extraction Test ===")
    print(f"Title: {result['title']}")
    print(f"Metadata: {result['metadata']}")
    print(f"\nContent:\n{result['content']}")

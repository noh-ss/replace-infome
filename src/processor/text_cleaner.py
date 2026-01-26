"""
텍스트 정제기
HTML에서 추출된 텍스트를 정제하고 정규화
"""

import re
from typing import Optional


class TextCleaner:
    """텍스트 정제 및 정규화"""

    def __init__(self):
        """TextCleaner 초기화"""
        # 여러 공백을 하나로 줄이기 위한 패턴
        self.whitespace_pattern = re.compile(r'\s+')

        # 반복되는 특수문자 패턴
        self.repeated_chars_pattern = re.compile(r'([^\w\s가-힣])\1{2,}')

        # URL 패턴 (선택적 제거)
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

    def clean(self, text: str, remove_urls: bool = False) -> str:
        """
        텍스트 정제

        Args:
            text: 정제할 텍스트
            remove_urls: URL 제거 여부

        Returns:
            정제된 텍스트
        """
        if not text:
            return ""

        # 1. 유니코드 정규화
        text = self._normalize_unicode(text)

        # 2. HTML 엔티티 디코딩 (만약 남아있다면)
        text = self._decode_html_entities(text)

        # 3. URL 제거 (옵션)
        if remove_urls:
            text = self.url_pattern.sub('', text)

        # 4. 반복되는 특수문자 제거 (예: "!!!!!!" -> "!")
        text = self.repeated_chars_pattern.sub(r'\1', text)

        # 5. 여러 줄바꿈을 최대 2개로 제한
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 6. 공백 정규화
        text = self._normalize_whitespace(text)

        # 7. 앞뒤 공백 제거
        text = text.strip()

        # 8. 보일러플레이트 제거 (선택적)
        text = self._remove_boilerplate(text)

        return text

    def _normalize_unicode(self, text: str) -> str:
        """유니코드 정규화 (NFC)"""
        import unicodedata
        return unicodedata.normalize('NFC', text)

    def _decode_html_entities(self, text: str) -> str:
        """HTML 엔티티 디코딩"""
        import html
        return html.unescape(text)

    def _normalize_whitespace(self, text: str) -> str:
        """
        공백 정규화
        - 여러 공백을 하나로
        - 탭을 공백으로
        - 줄바꿈은 보존
        """
        # 줄바꿈을 임시로 보호
        text = text.replace('\n', '___NEWLINE___')

        # 모든 공백을 하나로
        text = self.whitespace_pattern.sub(' ', text)

        # 줄바꿈 복원
        text = text.replace('___NEWLINE___', '\n')

        # 줄 시작/끝 공백 제거
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)

        return text

    def _remove_boilerplate(self, text: str) -> str:
        """
        보일러플레이트 텍스트 제거
        (예: "페이지를 찾을 수 없습니다", "JavaScript를 활성화하세요" 등)
        """
        boilerplate_patterns = [
            r'페이지를 찾을 수 없습니다.*?',
            r'JavaScript를 활성화.*?',
            r'쿠키를 활성화.*?',
            r'Copyright.*?\d{4}.*?',
            r'All rights reserved.*?',
            r'본 사이트는.*?권장합니다.*?',
        ]

        for pattern in boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)

        return text

    def clean_title(self, title: str) -> str:
        """
        제목 정제 (더 엄격한 정제)

        Args:
            title: 정제할 제목

        Returns:
            정제된 제목
        """
        if not title:
            return ""

        # 기본 정제
        title = self._normalize_unicode(title)
        title = self._decode_html_entities(title)

        # 제목에서 사이트명 제거 (예: "입학안내 - 경상국립대학교" -> "입학안내")
        title = re.sub(r'\s*[-|]\s*경상국립대학교.*?$', '', title)
        title = re.sub(r'\s*[-|]\s*GNU.*?$', '', title, flags=re.IGNORECASE)

        # 공백 정규화
        title = self.whitespace_pattern.sub(' ', title)
        title = title.strip()

        return title

    def is_valid_content(self, text: str, min_length: int = 100) -> bool:
        """
        콘텐츠 유효성 검사

        Args:
            text: 검사할 텍스트
            min_length: 최소 길이

        Returns:
            유효 여부
        """
        if not text or len(text) < min_length:
            return False

        # 한글이 포함되어 있는지 확인
        if not re.search(r'[가-힣]', text):
            return False

        # 단어 수 확인 (최소 10단어)
        words = text.split()
        if len(words) < 10:
            return False

        return True


if __name__ == "__main__":
    # TextCleaner 테스트
    cleaner = TextCleaner()

    # 테스트 텍스트
    test_text = """
    경상국립대학교    입학안내


    2024학년도   신입생   모집요강입니다!!!!!!


    자세한    내용은
    https://gnu.ac.kr/admission/2024


    문의: 055-772-0000


    Copyright 2024 GNU. All rights reserved.
    """

    print("=== 원본 텍스트 ===")
    print(test_text)
    print()

    # 정제
    cleaned = cleaner.clean(test_text, remove_urls=True)
    print("=== 정제된 텍스트 ===")
    print(cleaned)
    print()

    # 제목 정제
    test_title = "입학안내 - 경상국립대학교 GNU"
    cleaned_title = cleaner.clean_title(test_title)
    print(f"=== 제목 정제 ===")
    print(f"원본: {test_title}")
    print(f"정제: {cleaned_title}")
    print()

    # 유효성 검사
    is_valid = cleaner.is_valid_content(cleaned)
    print(f"=== 유효성 검사 ===")
    print(f"유효 여부: {is_valid}")

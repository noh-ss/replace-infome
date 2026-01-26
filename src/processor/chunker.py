"""
텍스트 청커
긴 텍스트를 의미 있는 청크로 분할
"""

from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter

from config.settings import settings
from src.utils.logger import get_processor_logger


logger = get_processor_logger()


class TextChunker:
    """LangChain 기반 텍스트 청커"""

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        length_function: callable = len
    ):
        """
        TextChunker 초기화

        Args:
            chunk_size: 청크 크기 (기본값: settings에서 가져옴)
            chunk_overlap: 청크 오버랩 (기본값: settings에서 가져옴)
            length_function: 길이 측정 함수
        """
        self.chunk_size = chunk_size or settings.rag.chunk_size
        self.chunk_overlap = chunk_overlap or settings.rag.chunk_overlap
        self.length_function = length_function

        # 한글 친화적인 구분자 설정
        self.separators = [
            "\n\n",      # 단락 구분
            "\n",        # 줄바꿈
            ". ",        # 영어 문장
            "。 ",       # 일본어/중국어 문장
            "? ",        # 질문
            "! ",        # 감탄
            ";",         # 세미콜론
            ",",         # 쉼표
            " ",         # 공백
            ""           # 마지막 수단
        ]

        # RecursiveCharacterTextSplitter 초기화
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self.length_function,
            separators=self.separators,
            keep_separator=True
        )

        logger.info(
            f"TextChunker initialized: chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def split_text(self, text: str) -> List[str]:
        """
        텍스트를 청크로 분할

        Args:
            text: 분할할 텍스트

        Returns:
            청크 목록
        """
        if not text:
            return []

        # LangChain splitter 사용
        chunks = self.splitter.split_text(text)

        # 빈 청크 제거
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

        # 너무 짧은 청크 필터링 (최소 50자)
        min_chunk_length = 50
        chunks = [chunk for chunk in chunks if len(chunk) >= min_chunk_length]

        logger.debug(f"Split text into {len(chunks)} chunks")

        return chunks

    def split_documents(self, texts: List[str]) -> List[str]:
        """
        여러 문서를 청크로 분할

        Args:
            texts: 문서 목록

        Returns:
            모든 문서의 청크 목록
        """
        all_chunks = []

        for text in texts:
            chunks = self.split_text(text)
            all_chunks.extend(chunks)

        logger.info(f"Split {len(texts)} documents into {len(all_chunks)} chunks")

        return all_chunks

    def get_chunk_info(self, chunks: List[str]) -> dict:
        """
        청크 통계 정보

        Args:
            chunks: 청크 목록

        Returns:
            통계 딕셔너리
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "total_characters": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0
            }

        chunk_sizes = [len(chunk) for chunk in chunks]

        return {
            "total_chunks": len(chunks),
            "total_characters": sum(chunk_sizes),
            "avg_chunk_size": sum(chunk_sizes) / len(chunks),
            "min_chunk_size": min(chunk_sizes),
            "max_chunk_size": max(chunk_sizes)
        }


class KoreanSentenceChunker:
    """
    한국어 문장 기반 청커
    (선택적 대안 - 문장 단위로 더 정확하게 분할)
    """

    def __init__(self, max_chunk_size: int = 1000, overlap_sentences: int = 1):
        """
        KoreanSentenceChunker 초기화

        Args:
            max_chunk_size: 최대 청크 크기
            overlap_sentences: 오버랩할 문장 수
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences

        # 한국어 문장 끝 패턴
        import re
        self.sentence_pattern = re.compile(r'([^.!?\n]*[.!?\n]+)')

    def split_text(self, text: str) -> List[str]:
        """
        문장 단위로 텍스트 분할

        Args:
            text: 분할할 텍스트

        Returns:
            청크 목록
        """
        if not text:
            return []

        # 문장 분리
        sentences = self.sentence_pattern.findall(text)

        if not sentences:
            # 패턴이 없으면 전체를 하나의 청크로
            return [text] if len(text) <= self.max_chunk_size else [text]

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_len = len(sentence)

            # 현재 청크에 추가하면 크기 초과하는 경우
            if current_size + sentence_len > self.max_chunk_size and current_chunk:
                # 현재 청크 저장
                chunks.append(' '.join(current_chunk))

                # 오버랩을 위해 마지막 N개 문장 유지
                if self.overlap_sentences > 0:
                    overlap = current_chunk[-self.overlap_sentences:]
                    current_chunk = overlap
                    current_size = sum(len(s) for s in overlap)
                else:
                    current_chunk = []
                    current_size = 0

            # 문장 추가
            current_chunk.append(sentence)
            current_size += sentence_len

        # 마지막 청크
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        # 최소 길이 필터링
        chunks = [chunk for chunk in chunks if len(chunk) >= 50]

        return chunks


if __name__ == "__main__":
    # TextChunker 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    chunker = TextChunker()

    # 테스트 텍스트 (긴 텍스트)
    test_text = """
    경상국립대학교는 대한민국의 국립대학교입니다. 1948년에 설립되었으며, 경상남도 진주시에 본캠퍼스가 있습니다.

    경상국립대학교는 다양한 학부와 대학원 과정을 제공하고 있습니다. 인문대학, 사회과학대학, 자연과학대학, 공과대학,
    농업생명과학대학, 법과대학, 사범대학, 경영대학, 의과대학, 수의과대학, 해양과학대학 등 11개 단과대학과
    7개 대학원으로 구성되어 있습니다.

    학교는 교육, 연구, 사회봉사를 핵심 가치로 삼고 있습니다. 특히 지역사회와 긴밀한 협력 관계를 유지하며
    지역 발전에 기여하고 있습니다. 또한 국제화 교육을 강화하여 글로벌 인재 양성에 힘쓰고 있습니다.

    캠퍼스는 아름다운 자연환경 속에 위치해 있으며, 최신 교육시설과 연구시설을 갖추고 있습니다.
    도서관, 박물관, 체육관, 기숙사 등 다양한 편의시설이 마련되어 있어 학생들의 학업과 생활을 지원합니다.

    경상국립대학교는 지속적인 발전을 통해 대한민국을 대표하는 국립대학교로 성장하고 있습니다.
    """ * 3  # 텍스트를 3배로 늘려서 테스트

    print("=== RecursiveCharacterTextSplitter 테스트 ===")
    print(f"원본 텍스트 길이: {len(test_text)} 문자\n")

    chunks = chunker.split_text(test_text)

    print(f"생성된 청크 수: {len(chunks)}\n")

    for i, chunk in enumerate(chunks, 1):
        print(f"--- Chunk {i} ({len(chunk)} 문자) ---")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        print()

    # 통계 정보
    info = chunker.get_chunk_info(chunks)
    print("=== 청크 통계 ===")
    for key, value in info.items():
        if isinstance(value, float):
            print(f"{key}: {value:.1f}")
        else:
            print(f"{key}: {value}")
    print()

    # 한국어 문장 청커 테스트
    print("\n=== KoreanSentenceChunker 테스트 ===")
    korean_chunker = KoreanSentenceChunker(max_chunk_size=500, overlap_sentences=1)
    korean_chunks = korean_chunker.split_text(test_text)

    print(f"생성된 청크 수: {len(korean_chunks)}\n")

    for i, chunk in enumerate(korean_chunks, 1):
        print(f"--- Chunk {i} ({len(chunk)} 문자) ---")
        print(chunk[:200] + "..." if len(chunk) > 200 else chunk)
        print()

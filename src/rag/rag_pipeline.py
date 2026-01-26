"""
RAG 파이프라인
검색 + 생성을 통합한 질의응답 시스템
"""

from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass

from config.settings import settings
from src.rag.retriever import Retriever, RetrievedDocument
from src.rag.llm_interface import LLMInterface
from src.utils.logger import get_rag_logger


logger = get_rag_logger()


@dataclass
class RAGResponse:
    """RAG 응답 데이터 클래스"""
    question: str
    answer: str
    sources: List[Dict[str, str]]
    retrieved_documents: List[RetrievedDocument]

    def __str__(self):
        sources_str = "\n".join([f"  - {s['title']}" for s in self.sources])
        return f"Question: {self.question}\nAnswer: {self.answer}\nSources:\n{sources_str}"


class RAGPipeline:
    """RAG 파이프라인"""

    def __init__(
        self,
        collection_name: str = "gnu_knowledge_base",
        model: Optional[str] = None
    ):
        """
        RAGPipeline 초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
            model: LLM 모델 이름
        """
        self.collection_name = collection_name
        self.model = model

        # 컴포넌트 초기화
        self.retriever = Retriever(collection_name=collection_name)
        self.llm = LLMInterface(model=model)

        logger.info(f"RAGPipeline initialized: collection={collection_name}, model={self.llm.model}")

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        temperature: float = 0.7,
        stream: bool = False
    ) -> RAGResponse:
        """
        질의응답 실행

        Args:
            question: 사용자 질문
            top_k: 검색할 문서 수
            temperature: LLM 온도
            stream: 스트리밍 여부

        Returns:
            RAGResponse
        """
        if not question or not question.strip():
            logger.warning("Empty question provided")
            return RAGResponse(
                question=question,
                answer="질문을 입력해주세요.",
                sources=[],
                retrieved_documents=[]
            )

        logger.info(f"Processing question: '{question[:100]}...'")

        try:
            # 1. 문서 검색
            logger.info("Step 1: Retrieving relevant documents...")
            documents = self.retriever.retrieve(question, top_k=top_k)

            if not documents:
                logger.warning("No relevant documents found")
                return RAGResponse(
                    question=question,
                    answer="죄송합니다. 관련된 정보를 찾을 수 없습니다. 다른 질문을 시도해주세요.",
                    sources=[],
                    retrieved_documents=[]
                )

            logger.info(f"Retrieved {len(documents)} documents")

            # 2. 컨텍스트 생성
            logger.info("Step 2: Building context...")
            context = self.retriever.get_context_text(documents, include_metadata=True)
            logger.debug(f"Context length: {len(context)} characters")

            # 3. LLM 생성
            logger.info("Step 3: Generating answer...")
            answer = self.llm.generate(
                prompt=question,
                context=context,
                stream=stream,
                temperature=temperature
            )

            logger.info("Answer generated successfully")

            # 4. 출처 정보 추출
            sources = self.retriever.get_sources(documents)

            # 5. 응답 구성
            response = RAGResponse(
                question=question,
                answer=answer,
                sources=sources,
                retrieved_documents=documents
            )

            return response

        except Exception as e:
            logger.error(f"RAG pipeline failed: {str(e)}", exc_info=True)
            return RAGResponse(
                question=question,
                answer=f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}",
                sources=[],
                retrieved_documents=[]
            )

    def query_stream(
        self,
        question: str,
        top_k: Optional[int] = None,
        temperature: float = 0.7
    ) -> Generator[str, None, None]:
        """
        스트리밍 질의응답

        Args:
            question: 사용자 질문
            top_k: 검색할 문서 수
            temperature: LLM 온도

        Yields:
            생성된 텍스트 청크
        """
        if not question or not question.strip():
            yield "질문을 입력해주세요."
            return

        logger.info(f"Processing streaming question: '{question[:100]}...'")

        try:
            # 1. 문서 검색
            documents = self.retriever.retrieve(question, top_k=top_k)

            if not documents:
                yield "죄송합니다. 관련된 정보를 찾을 수 없습니다."
                return

            # 2. 컨텍스트 생성
            context = self.retriever.get_context_text(documents, include_metadata=True)

            # 3. LLM 스트리밍 생성
            for chunk in self.llm.generate_stream(
                prompt=question,
                context=context,
                temperature=temperature
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Streaming RAG pipeline failed: {str(e)}")
            yield f"죄송합니다. 응답 생성 중 오류가 발생했습니다."

    def get_related_questions(self, question: str, n: int = 3) -> List[str]:
        """
        연관 질문 제안

        Args:
            question: 원래 질문
            n: 제안할 질문 수

        Returns:
            연관 질문 리스트
        """
        # 간단한 구현: 검색된 문서의 제목을 기반으로 질문 생성
        documents = self.retriever.retrieve(question, top_k=n)

        related = []
        for doc in documents:
            title = doc.metadata.get('title', '')
            if title and title not in related:
                # 제목에서 질문 생성
                if '안내' in title:
                    related.append(f"{title.replace('안내', '')}에 대해 알려주세요")
                elif '모집' in title:
                    related.append(f"{title.replace('모집', '')} 지원 방법은?")
                else:
                    related.append(f"{title}에 대해 설명해주세요")

        return related[:n]


if __name__ == "__main__":
    # RAGPipeline 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    print("=== RAGPipeline 테스트 ===\n")

    # RAG 파이프라인 초기화
    rag = RAGPipeline()

    # 테스트 질문들
    test_questions = [
        "경상국립대학교 입학 안내에 대해 알려주세요",
        "등록금 납부 방법은 무엇인가요?",
        "기초학력진단평가는 언제 응시하나요?"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n{'=' * 80}")
        print(f"질문 {i}: {question}")
        print('=' * 80)

        # RAG 쿼리 실행
        response = rag.query(question, top_k=3)

        print(f"\n[답변]")
        print(response.answer)

        print(f"\n[출처] ({len(response.sources)}개)")
        for j, source in enumerate(response.sources, 1):
            print(f"{j}. {source['title']}")
            print(f"   URL: {source['url']}")
            print(f"   유사도: {source['score']}")

        # 연관 질문
        related = rag.get_related_questions(question, n=2)
        if related:
            print(f"\n[연관 질문]")
            for rq in related:
                print(f"  - {rq}")

    print(f"\n{'=' * 80}")

    # 스트리밍 테스트
    print("\n=== 스트리밍 테스트 ===\n")
    print("질문: 경상국립대학교에 대해 간단히 설명해주세요")
    print("\n답변: ", end="", flush=True)

    for chunk in rag.query_stream("경상국립대학교에 대해 간단히 설명해주세요", top_k=2):
        print(chunk, end="", flush=True)

    print("\n\n✅ 테스트 완료!")

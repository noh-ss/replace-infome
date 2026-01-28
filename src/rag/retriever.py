"""
문서 검색기
벡터 스토어에서 쿼리와 관련된 문서 검색
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config.settings import settings
from src.vectorstore.chroma_manager import ChromaManager
from src.utils.logger import get_rag_logger


logger = get_rag_logger()


@dataclass
class RetrievedDocument:
    """검색된 문서 데이터 클래스"""
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float  # 유사도 점수 (낮을수록 유사)

    def __str__(self):
        return f"Document(id={self.id}, score={self.score:.4f}, text={self.text[:100]}...)"


class Retriever:
    """벡터 스토어 기반 문서 검색기"""

    def __init__(
        self,
        collection_name: str = "gnu_knowledge_base",
        top_k: int = None,
        similarity_threshold: float = None
    ):
        """
        Retriever 초기화

        Args:
            collection_name: ChromaDB 컬렉션 이름
            top_k: 반환할 최대 문서 수
            similarity_threshold: 유사도 임계값
        """
        self.collection_name = collection_name
        self.top_k = top_k or settings.rag.top_k_retrieval
        self.similarity_threshold = similarity_threshold or settings.rag.similarity_threshold

        # ChromaManager 초기화
        self.chroma_manager = ChromaManager(collection_name=collection_name)

        logger.info(
            f"Retriever initialized: collection={collection_name}, "
            f"top_k={self.top_k}, threshold={self.similarity_threshold}"
        )

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievedDocument]:
        """
        쿼리와 관련된 문서 검색 (하이브리드: 시맨틱 + 키워드)

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수 (기본값: self.top_k)
            filters: 메타데이터 필터

        Returns:
            검색된 문서 리스트
        """
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return []

        k = top_k or self.top_k

        logger.info(f"Retrieving documents for query: '{query[:100]}...'")

        try:
            # ChromaDB 검색 (더 많은 결과를 가져와서 키워드 매칭으로 재정렬)
            search_k = max(k * 5, 50)  # 최소 50개 또는 k*5개 검색
            results = self.chroma_manager.query(
                query_text=query,
                n_results=search_k,
                where=filters
            )

            # 결과 파싱
            documents = self._parse_results(results)

            # 키워드 매칭으로 점수 조정 (하이브리드 검색)
            query_terms = query.lower().split()
            for doc in documents:
                text_lower = doc.text.lower()
                # 쿼리 단어가 문서에 포함되면 점수 보너스 (점수가 낮을수록 좋음)
                keyword_matches = sum(1 for term in query_terms if term in text_lower)
                if keyword_matches > 0:
                    # 키워드 매칭 시 점수를 크게 낮춤 (우선순위 상승)
                    doc.score = doc.score * (0.3 ** keyword_matches)

            # 점수로 재정렬 (낮을수록 좋음)
            documents.sort(key=lambda x: x.score)

            # 유사도 임계값 필터링 및 top_k 적용
            filtered_docs = [
                doc for doc in documents[:k]
                if doc.score <= self.similarity_threshold * 1000
            ]

            logger.info(f"Retrieved {len(documents)} documents, {len(filtered_docs)} after filtering")

            return filtered_docs

        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}")
            return []

    def _parse_results(self, results: Dict[str, Any]) -> List[RetrievedDocument]:
        """
        ChromaDB 검색 결과를 RetrievedDocument로 변환

        Args:
            results: ChromaDB 검색 결과

        Returns:
            RetrievedDocument 리스트
        """
        documents = []

        if not results or not results.get('ids'):
            return documents

        ids = results['ids'][0]
        texts = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        for doc_id, text, metadata, distance in zip(ids, texts, metadatas, distances):
            doc = RetrievedDocument(
                id=doc_id,
                text=text,
                metadata=metadata,
                score=distance
            )
            documents.append(doc)

        return documents

    def retrieve_by_category(
        self,
        query: str,
        category: str,
        top_k: Optional[int] = None
    ) -> List[RetrievedDocument]:
        """
        특정 카테고리에서 문서 검색

        Args:
            query: 검색 쿼리
            category: 카테고리 필터
            top_k: 반환할 문서 수

        Returns:
            검색된 문서 리스트
        """
        filters = {"category": category}
        return self.retrieve(query, top_k=top_k, filters=filters)

    def get_context_text(
        self,
        documents: List[RetrievedDocument],
        include_metadata: bool = True
    ) -> str:
        """
        검색된 문서들을 컨텍스트 텍스트로 변환

        Args:
            documents: 검색된 문서 리스트
            include_metadata: 메타데이터 포함 여부

        Returns:
            컨텍스트 텍스트
        """
        if not documents:
            return ""

        context_parts = []

        for i, doc in enumerate(documents, 1):
            part = f"[문서 {i}]"

            if include_metadata:
                title = doc.metadata.get('title', 'Unknown')
                source = doc.metadata.get('source_url', 'Unknown')
                part += f"\n제목: {title}\n출처: {source}"

            part += f"\n내용: {doc.text}\n"

            context_parts.append(part)

        context = "\n".join(context_parts)

        logger.debug(f"Generated context with {len(documents)} documents, {len(context)} characters")

        return context

    def get_sources(self, documents: List[RetrievedDocument]) -> List[Dict[str, str]]:
        """
        검색된 문서의 출처 정보 추출

        Args:
            documents: 검색된 문서 리스트

        Returns:
            출처 정보 리스트
        """
        sources = []

        for doc in documents:
            source = {
                "title": doc.metadata.get('title', 'Unknown'),
                "url": doc.metadata.get('source_url', ''),
                "score": f"{doc.score:.4f}"
            }
            sources.append(source)

        return sources


if __name__ == "__main__":
    # Retriever 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    print("=== Retriever 테스트 ===\n")

    # Retriever 초기화
    retriever = Retriever()

    # 테스트 쿼리
    test_queries = [
        "경상국립대학교 입학 안내",
        "도서관 이용 시간",
        "장학금 신청 방법",
        "등록금 납부 안내"
    ]

    for query in test_queries:
        print(f"\n{'=' * 80}")
        print(f"쿼리: {query}")
        print('=' * 80)

        # 문서 검색
        documents = retriever.retrieve(query, top_k=3)

        print(f"검색 결과: {len(documents)}개 문서\n")

        for i, doc in enumerate(documents, 1):
            print(f"[문서 {i}]")
            print(f"ID: {doc.id}")
            print(f"유사도 점수: {doc.score:.4f}")
            print(f"제목: {doc.metadata.get('title', 'N/A')}")
            print(f"출처: {doc.metadata.get('source_url', 'N/A')}")
            print(f"내용 (처음 200자): {doc.text[:200]}...")
            print()

        # 컨텍스트 생성
        context = retriever.get_context_text(documents)
        print(f"컨텍스트 길이: {len(context)} 문자")

        # 출처 추출
        sources = retriever.get_sources(documents)
        print(f"\n출처 정보:")
        for source in sources:
            print(f"  - {source['title']} (점수: {source['score']})")

    print(f"\n{'=' * 80}")
    print("✅ 테스트 완료!")

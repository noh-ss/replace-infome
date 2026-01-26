"""
ChromaDB 관리자
벡터 데이터베이스 생성, 저장, 검색
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from config.settings import settings
from src.utils.logger import get_vectorstore_logger
from src.vectorstore.embedding_service import EmbeddingService


logger = get_vectorstore_logger()


class ChromaManager:
    """ChromaDB 벡터 스토어 관리"""

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: str = "gnu_knowledge_base"
    ):
        """
        ChromaManager 초기화

        Args:
            persist_directory: ChromaDB 저장 경로
            collection_name: 컬렉션 이름
        """
        self.persist_directory = persist_directory or settings.vector_store_dir
        self.collection_name = collection_name

        # 디렉토리 생성
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # 임베딩 서비스 초기화
        self.embedding_service = EmbeddingService()

        # 컬렉션 (lazy initialization)
        self._collection = None

        logger.info(
            f"ChromaManager initialized: persist_dir={self.persist_directory}, "
            f"collection={self.collection_name}"
        )

    def get_or_create_collection(self) -> chromadb.Collection:
        """
        컬렉션 가져오기 또는 생성

        Returns:
            ChromaDB 컬렉션
        """
        if self._collection is not None:
            return self._collection

        try:
            # 기존 컬렉션 가져오기
            self._collection = self.client.get_collection(
                name=self.collection_name
            )
            logger.info(f"Loaded existing collection: {self.collection_name}")

        except Exception:
            # 컬렉션이 없으면 새로 생성
            self._collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "GNU RAG Knowledge Base"}
            )
            logger.info(f"Created new collection: {self.collection_name}")

        return self._collection

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 100
    ) -> int:
        """
        문서를 벡터 스토어에 추가

        Args:
            documents: 문서 텍스트 목록
            metadatas: 메타데이터 목록
            ids: 문서 ID 목록
            batch_size: 배치 크기

        Returns:
            추가된 문서 수
        """
        if not documents or len(documents) == 0:
            logger.warning("No documents to add")
            return 0

        if not (len(documents) == len(metadatas) == len(ids)):
            raise ValueError("documents, metadatas, and ids must have the same length")

        collection = self.get_or_create_collection()
        total_docs = len(documents)

        logger.info(f"Adding {total_docs} documents to collection...")

        added_count = 0

        for i in range(0, total_docs, batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]

            batch_start = i + 1
            batch_end = min(i + batch_size, total_docs)

            logger.info(f"Processing batch {batch_start}-{batch_end}/{total_docs}")

            try:
                # 임베딩 생성
                embeddings = self.embedding_service.embed_batch(batch_docs)

                # ChromaDB에 추가
                collection.add(
                    documents=batch_docs,
                    metadatas=batch_metas,
                    ids=batch_ids,
                    embeddings=embeddings
                )

                added_count += len(batch_docs)
                logger.info(f"Successfully added batch {batch_start}-{batch_end}")

            except Exception as e:
                logger.error(f"Error adding batch {batch_start}-{batch_end}: {str(e)}")
                continue

        logger.info(f"Total documents added: {added_count}/{total_docs}")

        return added_count

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        유사도 검색

        Args:
            query_text: 검색 쿼리
            n_results: 반환할 결과 수
            where: 메타데이터 필터

        Returns:
            검색 결과
        """
        collection = self.get_or_create_collection()

        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_service.embed_text(query_text)

            # 검색 실행
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where
            )

            logger.info(f"Query returned {len(results['ids'][0])} results")

            return results

        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        컬렉션 통계 정보

        Returns:
            통계 딕셔너리
        """
        collection = self.get_or_create_collection()

        try:
            count = collection.count()

            stats = {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory)
            }

            logger.info(f"Collection stats: {stats}")

            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {}

    def delete_collection(self) -> bool:
        """
        컬렉션 삭제

        Returns:
            삭제 성공 여부
        """
        try:
            self.client.delete_collection(name=self.collection_name)
            self._collection = None
            logger.info(f"Deleted collection: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection: {str(e)}")
            return False

    def reset(self) -> bool:
        """
        전체 데이터베이스 리셋

        Returns:
            리셋 성공 여부
        """
        try:
            self.client.reset()
            self._collection = None
            logger.warning("Database reset completed")
            return True

        except Exception as e:
            logger.error(f"Failed to reset database: {str(e)}")
            return False

    def get_document_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        ID로 문서 가져오기

        Args:
            doc_id: 문서 ID

        Returns:
            문서 데이터 또는 None
        """
        collection = self.get_or_create_collection()

        try:
            result = collection.get(ids=[doc_id])

            if result and result['ids']:
                return {
                    "id": result['ids'][0],
                    "document": result['documents'][0],
                    "metadata": result['metadatas'][0] if result['metadatas'] else {}
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {str(e)}")
            return None

    def list_collections(self) -> List[str]:
        """
        모든 컬렉션 목록

        Returns:
            컬렉션 이름 목록
        """
        try:
            collections = self.client.list_collections()
            collection_names = [c.name for c in collections]

            logger.info(f"Found {len(collection_names)} collections")

            return collection_names

        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            return []


if __name__ == "__main__":
    # ChromaManager 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    print("=== ChromaManager 테스트 ===\n")

    # 테스트용 임시 디렉토리
    test_dir = PROJECT_ROOT / "data" / "vector_store_test"

    # ChromaManager 초기화
    manager = ChromaManager(
        persist_directory=test_dir,
        collection_name="test_collection"
    )

    print("1. 컬렉션 생성")
    collection = manager.get_or_create_collection()
    print(f"컬렉션 이름: {collection.name}\n")

    print("2. 컬렉션 목록")
    collections = manager.list_collections()
    print(f"컬렉션: {collections}\n")

    print("3. 문서 추가")
    test_documents = [
        "경상국립대학교는 1948년에 설립된 국립대학교입니다.",
        "도서관은 평일 오전 9시부터 오후 10시까지 운영됩니다.",
        "장학금 신청은 매 학기 초에 진행됩니다.",
    ]

    test_metadatas = [
        {"source": "about", "category": "general"},
        {"source": "library", "category": "facilities"},
        {"source": "scholarship", "category": "finance"},
    ]

    test_ids = ["doc_001", "doc_002", "doc_003"]

    added = manager.add_documents(
        documents=test_documents,
        metadatas=test_metadatas,
        ids=test_ids
    )
    print(f"추가된 문서: {added}개\n")

    print("4. 컬렉션 통계")
    stats = manager.get_collection_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()

    print("5. 유사도 검색")
    query = "도서관 운영 시간은?"
    results = manager.query(query, n_results=2)

    print(f"쿼리: {query}")
    print(f"결과 수: {len(results['ids'][0])}")

    for i, (doc_id, doc, metadata, distance) in enumerate(
        zip(
            results['ids'][0],
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ),
        1
    ):
        print(f"\n결과 {i}:")
        print(f"  ID: {doc_id}")
        print(f"  문서: {doc}")
        print(f"  메타데이터: {metadata}")
        print(f"  거리: {distance:.4f}")

    print("\n6. ID로 문서 가져오기")
    doc = manager.get_document_by_id("doc_002")
    if doc:
        print(f"ID: {doc['id']}")
        print(f"문서: {doc['document']}")
        print(f"메타데이터: {doc['metadata']}")

    print("\n7. 컬렉션 삭제")
    deleted = manager.delete_collection()
    print(f"삭제 성공: {deleted}")

    print("\n✅ 테스트 완료!")

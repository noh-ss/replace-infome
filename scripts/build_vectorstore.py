#!/usr/bin/env python
"""
벡터 스토어 구축 스크립트
처리된 청크를 읽어 ChromaDB에 임베딩 및 저장
"""

import sys
import json
from pathlib import Path
from typing import List, Dict

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.vectorstore.chroma_manager import ChromaManager
from src.utils.logger import get_vectorstore_logger

logger = get_vectorstore_logger()


def load_chunks(chunks_file: Path) -> List[Dict]:
    """
    JSONL 파일에서 청크 로드

    Args:
        chunks_file: chunks.jsonl 파일 경로

    Returns:
        청크 목록
    """
    logger.info(f"Loading chunks from {chunks_file}")

    if not chunks_file.exists():
        logger.error(f"Chunks file not found: {chunks_file}")
        raise FileNotFoundError(f"Chunks file not found: {chunks_file}")

    chunks = []

    with open(chunks_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)
                chunks.append(chunk)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error at line {line_num}: {str(e)}")
                continue

    logger.info(f"Loaded {len(chunks)} chunks")

    return chunks


def prepare_documents(chunks: List[Dict]) -> tuple:
    """
    ChromaDB 형식으로 문서 준비

    Args:
        chunks: 청크 목록

    Returns:
        (documents, metadatas, ids) 튜플
    """
    logger.info("Preparing documents for ChromaDB...")

    documents = []
    metadatas = []
    ids = []

    for chunk in chunks:
        # 텍스트
        text = chunk.get("text", "")

        if not text or len(text) < 10:
            logger.warning(f"Skipping chunk {chunk.get('id')} - text too short")
            continue

        # 메타데이터
        metadata = chunk.get("metadata", {})

        # ChromaDB는 메타데이터로 문자열, 숫자, 불린만 허용
        # 복잡한 타입은 문자열로 변환
        clean_metadata = {}

        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean_metadata[key] = value
            else:
                clean_metadata[key] = str(value)

        # ID
        chunk_id = chunk.get("id", "")

        if not chunk_id:
            logger.warning("Chunk missing ID - skipping")
            continue

        documents.append(text)
        metadatas.append(clean_metadata)
        ids.append(chunk_id)

    logger.info(f"Prepared {len(documents)} documents")

    return documents, metadatas, ids


def build_vectorstore(chunks_file: Path, collection_name: str = "gnu_knowledge_base", reset: bool = False):
    """
    벡터 스토어 구축

    Args:
        chunks_file: chunks.jsonl 파일 경로
        collection_name: ChromaDB 컬렉션 이름
        reset: 기존 컬렉션 삭제 여부
    """
    logger.info("=" * 80)
    logger.info("Starting Vector Store Build")
    logger.info("=" * 80)

    # ChromaManager 초기화
    manager = ChromaManager(collection_name=collection_name)

    # 기존 컬렉션 삭제 (옵션)
    if reset:
        logger.warning("Resetting existing collection...")
        manager.delete_collection()

    # 청크 로드
    chunks = load_chunks(chunks_file)

    if not chunks:
        logger.error("No chunks to process!")
        return

    # 문서 준비
    documents, metadatas, ids = prepare_documents(chunks)

    if not documents:
        logger.error("No valid documents to add!")
        return

    # 벡터 스토어에 추가
    logger.info("-" * 80)
    logger.info("Adding documents to vector store...")
    logger.info("-" * 80)

    added_count = manager.add_documents(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
        batch_size=32
    )

    logger.info("=" * 80)
    logger.info("Vector Store Build Completed")
    logger.info("=" * 80)
    logger.info(f"Documents added: {added_count}/{len(documents)}")

    # 통계 출력
    stats = manager.get_collection_stats()
    logger.info("-" * 80)
    logger.info("Collection Statistics")
    logger.info("-" * 80)

    for key, value in stats.items():
        logger.info(f"{key}: {value}")

    logger.info("=" * 80)

    # 테스트 쿼리 실행
    logger.info("\n" + "=" * 80)
    logger.info("Test Query")
    logger.info("=" * 80)

    test_queries = [
        "경상국립대학교 입학 안내",
        "도서관 이용 시간",
        "장학금 신청"
    ]

    for query in test_queries:
        logger.info(f"\n쿼리: {query}")

        try:
            results = manager.query(query, n_results=3)

            if results and results['ids'][0]:
                logger.info(f"결과 수: {len(results['ids'][0])}")

                for i, (doc_id, doc_text, distance) in enumerate(
                    zip(
                        results['ids'][0],
                        results['documents'][0],
                        results['distances'][0]
                    ),
                    1
                ):
                    logger.info(f"\n  결과 {i}:")
                    logger.info(f"    ID: {doc_id}")
                    logger.info(f"    거리: {distance:.4f}")
                    logger.info(f"    텍스트: {doc_text[:100]}...")

        except Exception as e:
            logger.error(f"Query failed: {str(e)}")

    logger.info("\n" + "=" * 80)


def main(reset: bool = False):
    """메인 함수"""
    try:
        # 청크 파일 경로
        chunks_file = settings.processed_data_dir / "chunks.jsonl"

        # 벡터 스토어 구축
        build_vectorstore(chunks_file, reset=reset)

    except FileNotFoundError as e:
        logger.error(str(e))
        logger.info("\n먼저 데이터 처리를 실행하세요:")
        logger.info("  python scripts/process_data.py")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Vector store build failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build ChromaDB vector store")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing collection before building"
    )

    args = parser.parse_args()

    try:
        main(reset=args.reset)
    except KeyboardInterrupt:
        logger.info("\nVector store build interrupted by user")
    except Exception as e:
        logger.error(f"Build error: {str(e)}", exc_info=True)
        sys.exit(1)

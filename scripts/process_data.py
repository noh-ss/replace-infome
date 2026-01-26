#!/usr/bin/env python
"""
데이터 처리 스크립트
크롤링된 HTML을 텍스트 청크로 변환
"""

import sys
import json
from pathlib import Path
from typing import List, Dict
import uuid

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.crawler.content_extractor import ContentExtractor
from src.processor.text_cleaner import TextCleaner
from src.processor.chunker import TextChunker
from src.processor.metadata_manager import MetadataManager
from src.utils.logger import get_processor_logger

logger = get_processor_logger()


def process_html_files(max_files: int = None) -> List[Dict]:
    """
    HTML 파일들을 처리하여 청크 생성

    Args:
        max_files: 처리할 최대 파일 수

    Returns:
        생성된 청크 목록
    """
    logger.info("=" * 80)
    logger.info("Starting Data Processing")
    logger.info("=" * 80)

    # 초기화
    extractor = ContentExtractor()
    cleaner = TextCleaner()
    chunker = TextChunker()
    metadata_manager = MetadataManager()

    # HTML 파일 목록
    html_files = list(settings.raw_data_dir.glob("pages/*.html"))
    html_files.extend(list(settings.raw_data_dir.glob("bulletins/*.html")))

    if max_files:
        html_files = html_files[:max_files]

    logger.info(f"Found {len(html_files)} HTML files to process")

    all_chunks = []
    processed_count = 0
    failed_count = 0

    for idx, html_path in enumerate(html_files, 1):
        logger.info("-" * 80)
        logger.info(f"Processing [{idx}/{len(html_files)}]: {html_path.name}")

        try:
            # HTML 읽기
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # 메타 파일 읽기
            meta_path = html_path.with_suffix('.meta.txt')
            url = None
            if meta_path.exists():
                with open(meta_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('URL:'):
                            url = line.replace('URL:', '').strip()
                            break

            if not url:
                logger.warning(f"No URL found in metadata for {html_path.name}")
                url = f"file://{html_path}"

            # 콘텐츠 추출
            extracted = extractor.extract(html_content, url)

            # 텍스트 정제
            cleaned_text = cleaner.clean(extracted['content'])

            if not cleaned_text or len(cleaned_text) < 100:
                logger.warning(f"Text too short after cleaning: {len(cleaned_text)} chars")
                failed_count += 1
                continue

            # 청킹
            chunks = chunker.split_text(cleaned_text)

            logger.info(f"Generated {len(chunks)} chunks from {len(cleaned_text)} characters")

            # 메타데이터 추가
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_data = metadata_manager.create_chunk_metadata(
                    text=chunk_text,
                    url=url,
                    title=extracted['title'],
                    chunk_index=chunk_idx,
                    total_chunks=len(chunks),
                    metadata=extracted['metadata']
                )
                all_chunks.append(chunk_data)

            processed_count += 1

        except Exception as e:
            logger.error(f"Error processing {html_path.name}: {str(e)}")
            failed_count += 1
            continue

    logger.info("=" * 80)
    logger.info("Processing Completed")
    logger.info("=" * 80)
    logger.info(f"Files processed: {processed_count}")
    logger.info(f"Files failed: {failed_count}")
    logger.info(f"Total chunks created: {len(all_chunks)}")
    logger.info("=" * 80)

    return all_chunks


def save_chunks(chunks: List[Dict], output_file: Path):
    """청크를 JSONL 파일로 저장"""
    logger.info(f"Saving {len(chunks)} chunks to {output_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

    logger.info(f"Successfully saved to {output_file}")


def main(max_files: int = None):
    """메인 함수"""
    try:
        # 데이터 처리
        chunks = process_html_files(max_files=max_files)

        if not chunks:
            logger.warning("No chunks generated!")
            return

        # 저장
        output_file = settings.processed_data_dir / "chunks.jsonl"
        save_chunks(chunks, output_file)

        # 통계 출력
        logger.info("\n" + "=" * 80)
        logger.info("Statistics")
        logger.info("=" * 80)
        logger.info(f"Total chunks: {len(chunks)}")
        logger.info(f"Average chunk size: {sum(len(c['text']) for c in chunks) / len(chunks):.1f} chars")
        logger.info(f"Output file: {output_file}")
        logger.info(f"File size: {output_file.stat().st_size / (1024 * 1024):.2f} MB")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process crawled HTML data")
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to process"
    )

    args = parser.parse_args()

    main(max_files=args.max_files)

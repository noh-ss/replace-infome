#!/usr/bin/env python
"""
크롤러 실행 스크립트
gnu.ac.kr 웹사이트 크롤링
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.crawler.url_manager import URLManager
from src.crawler.page_scraper import PageScraper
from src.crawler.content_extractor import ContentExtractor
from src.utils.logger import get_crawler_logger

logger = get_crawler_logger()


def main(max_pages: int = 20):
    """
    크롤러 메인 함수

    Args:
        max_pages: 최대 크롤링 페이지 수
    """
    logger.info("=" * 80)
    logger.info("Starting GNU RAG Crawler")
    logger.info("=" * 80)

    # 초기화
    url_manager = URLManager()
    content_extractor = ContentExtractor()

    # 시작 URL 추가
    start_urls = settings.get_crawl_start_urls()
    logger.info(f"Start URLs: {start_urls}")

    for url in start_urls:
        url_manager.add_url(url, depth=0)

    # 크롤링
    pages_crawled = 0
    pages_failed = 0

    with PageScraper(headless=True) as scraper:
        while pages_crawled < max_pages:
            # 다음 URL 가져오기
            next_item = url_manager.get_next_url()

            if next_item is None:
                logger.info("No more URLs to crawl")
                break

            url, depth = next_item

            logger.info("-" * 80)
            logger.info(f"Crawling [{pages_crawled + 1}/{max_pages}]: {url} (depth={depth})")

            # 페이지 가져오기
            page_data = scraper.fetch_page(url)

            if page_data is None:
                url_manager.mark_visited(url, success=False, error_message="Failed to fetch")
                pages_failed += 1
                continue

            try:
                # HTML 저장
                html_path = scraper.save_html(url, page_data['html'])

                # 콘텐츠 추출
                extracted = content_extractor.extract(page_data['html'], url)

                logger.info(f"Title: {extracted['title']}")
                logger.info(f"Content length: {len(extracted['content'])} characters")

                # 링크 추출 및 큐에 추가
                added_links = url_manager.extract_links(url, page_data['links'], depth)
                logger.info(f"Added {added_links} new URLs to queue")

                # 방문 완료 표시
                url_manager.mark_visited(url, success=True)
                pages_crawled += 1

            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}")
                url_manager.mark_visited(url, success=False, error_message=str(e))
                pages_failed += 1

    # 최종 통계
    stats = url_manager.get_stats()

    logger.info("=" * 80)
    logger.info("Crawling Completed")
    logger.info("=" * 80)
    logger.info(f"Pages crawled: {pages_crawled}")
    logger.info(f"Pages failed: {pages_failed}")
    logger.info(f"Total URLs in database: {stats['total']}")
    logger.info(f"Pending URLs: {stats['pending']}")
    logger.info(f"Visited URLs: {stats['visited']}")
    logger.info(f"Failed URLs: {stats['failed']}")
    logger.info(f"Data saved to: {settings.raw_data_dir}")
    logger.info("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GNU RAG Crawler")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Maximum number of pages to crawl (default: 20)"
    )

    args = parser.parse_args()

    try:
        main(max_pages=args.max_pages)
    except KeyboardInterrupt:
        logger.info("\nCrawling interrupted by user")
    except Exception as e:
        logger.error(f"Crawler error: {str(e)}", exc_info=True)
        sys.exit(1)

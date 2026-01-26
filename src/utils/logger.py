"""
로깅 시스템
중앙집중식 로거 설정 및 관리
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.settings import settings


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: Optional[str] = None,
    console_output: bool = True
) -> logging.Logger:
    """
    로거 설정 및 반환

    Args:
        name: 로거 이름
        log_file: 로그 파일 이름 (기본값: {name}.log)
        level: 로그 레벨 (기본값: settings.logging.log_level)
        console_output: 콘솔 출력 여부

    Returns:
        설정된 로거 인스턴스
    """
    # 로거 생성
    logger = logging.getLogger(name)

    # 이미 핸들러가 있으면 반환 (중복 방지)
    if logger.handlers:
        return logger

    # 로그 레벨 설정
    log_level = level or settings.logging.log_level
    logger.setLevel(getattr(logging, log_level.upper()))

    # 로그 포맷 설정
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 파일 핸들러 추가
    if log_file:
        log_path = settings.logs_dir / log_file
    else:
        log_path = settings.logs_dir / f"{name}.log"

    # 로그 디렉토리 생성
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 로테이팅 파일 핸들러 (최대 10MB, 백업 5개)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 콘솔 핸들러 추가
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


# 미리 정의된 로거들
def get_crawler_logger() -> logging.Logger:
    """크롤러 로거 반환"""
    return setup_logger("crawler", log_file="crawler.log")


def get_processor_logger() -> logging.Logger:
    """프로세서 로거 반환"""
    return setup_logger("processor", log_file="processor.log")


def get_vectorstore_logger() -> logging.Logger:
    """벡터스토어 로거 반환"""
    return setup_logger("vectorstore", log_file="vectorstore.log")


def get_rag_logger() -> logging.Logger:
    """RAG 로거 반환"""
    return setup_logger("rag", log_file="rag.log")


def get_chatbot_logger() -> logging.Logger:
    """챗봇 로거 반환"""
    return setup_logger("chatbot", log_file="chatbot.log")


if __name__ == "__main__":
    # 로거 테스트
    test_logger = setup_logger("test")

    test_logger.debug("디버그 메시지")
    test_logger.info("정보 메시지")
    test_logger.warning("경고 메시지")
    test_logger.error("에러 메시지")
    test_logger.critical("치명적 에러 메시지")

    print(f"\n로그 파일 위치: {settings.logs_dir / 'test.log'}")

"""
중앙 설정 관리 시스템
Pydantic을 사용한 설정 검증 및 로딩
"""

from pathlib import Path
from typing import List

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent


class OllamaSettings(BaseSettings):
    """Ollama 설정"""
    base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    embedding_model: str = Field(default="nomic-embed-text", env="OLLAMA_EMBEDDING_MODEL")
    llm_model: str = Field(default="llama3.1", env="OLLAMA_LLM_MODEL")

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class ChromaDBSettings(BaseSettings):
    """ChromaDB 설정"""
    persist_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "vector_store" / "chroma",
        env="CHROMA_PERSIST_DIR"
    )

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class CrawlSettings(BaseSettings):
    """크롤링 설정"""
    start_url: str = Field(default="https://gnu.ac.kr", env="START_URL")
    max_crawl_depth: int = Field(default=5, env="MAX_CRAWL_DEPTH")
    crawl_rate_limit: float = Field(default=1.0, env="CRAWL_RATE_LIMIT")
    user_agent: str = Field(default="GNU-RAG-Bot/1.0", env="USER_AGENT")
    max_pages: int = Field(default=10000, env="MAX_PAGES")

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class RAGSettings(BaseSettings):
    """RAG 파이프라인 설정"""
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    top_k_retrieval: int = Field(default=5, env="TOP_K_RETRIEVAL")
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class LLMSettings(BaseSettings):
    """LLM 설정"""
    temperature: float = Field(default=0.1, env="LLM_TEMPERATURE")
    max_tokens: int = Field(default=2048, env="LLM_MAX_TOKENS")

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class LoggingSettings(BaseSettings):
    """로깅 설정"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_dir: Path = Field(default=PROJECT_ROOT / "logs", env="LOG_DIR")

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class Settings:
    """통합 설정 클래스"""

    def __init__(self):
        # 환경 변수 기반 설정
        self.ollama = OllamaSettings()
        self.chromadb = ChromaDBSettings()
        self.crawl = CrawlSettings()
        self.rag = RAGSettings()
        self.llm = LLMSettings()
        self.logging = LoggingSettings()

        # YAML 설정 파일 로드
        self.crawl_config = self._load_yaml_config("crawl_config.yaml")
        self.rag_config = self._load_yaml_config("rag_config.yaml")

        # 프로젝트 경로
        self.project_root = PROJECT_ROOT
        self.data_dir = PROJECT_ROOT / "data"
        self.raw_data_dir = self.data_dir / "raw"
        self.processed_data_dir = self.data_dir / "processed"
        self.vector_store_dir = self.data_dir / "vector_store"
        self.metadata_dir = self.data_dir / "metadata"
        self.logs_dir = self.logging.log_dir

        # 필요한 디렉토리 생성
        self._ensure_directories()

    def _load_yaml_config(self, filename: str) -> dict:
        """YAML 설정 파일 로드"""
        config_path = PROJECT_ROOT / "config" / filename
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _ensure_directories(self):
        """필요한 디렉토리 생성"""
        directories = [
            self.data_dir,
            self.raw_data_dir,
            self.raw_data_dir / "pages",
            self.raw_data_dir / "bulletins",
            self.processed_data_dir,
            self.vector_store_dir,
            self.metadata_dir,
            self.logs_dir,
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_crawl_start_urls(self) -> List[str]:
        """크롤링 시작 URL 목록 반환"""
        return self.crawl_config.get("start_urls", [self.crawl.start_url])

    def get_allowed_domains(self) -> List[str]:
        """허용된 도메인 목록 반환"""
        return self.crawl_config.get("filters", {}).get("allowed_domains", ["gnu.ac.kr"])

    def get_exclude_patterns(self) -> List[str]:
        """제외할 URL 패턴 목록 반환"""
        return self.crawl_config.get("filters", {}).get("exclude_patterns", [])

    def get_playwright_settings(self) -> dict:
        """Playwright 설정 반환"""
        return self.crawl_config.get("playwright_settings", {
            "headless": True,
            "wait_until": "networkidle",
        })

    def get_text_processing_settings(self) -> dict:
        """텍스트 처리 설정 반환"""
        return self.rag_config.get("text_processing", {
            "chunk_size": self.rag.chunk_size,
            "chunk_overlap": self.rag.chunk_overlap,
        })

    def get_retrieval_settings(self) -> dict:
        """검색 설정 반환"""
        return self.rag_config.get("retrieval", {
            "top_k": self.rag.top_k_retrieval,
            "similarity_threshold": self.rag.similarity_threshold,
        })

    def get_prompt_template(self) -> str:
        """프롬프트 템플릿 반환"""
        return self.rag_config.get("prompts", {}).get("user_prompt_template", "")


# 전역 설정 인스턴스
settings = Settings()


if __name__ == "__main__":
    # 설정 테스트
    print("=== GNU RAG Bot Settings ===")
    print(f"Project Root: {settings.project_root}")
    print(f"Ollama Base URL: {settings.ollama.base_url}")
    print(f"Ollama LLM Model: {settings.ollama.llm_model}")
    print(f"Ollama Embedding Model: {settings.ollama.embedding_model}")
    print(f"ChromaDB Persist Dir: {settings.chromadb.persist_dir}")
    print(f"Start URLs: {settings.get_crawl_start_urls()}")
    print(f"Max Crawl Depth: {settings.crawl.max_crawl_depth}")
    print(f"Chunk Size: {settings.rag.chunk_size}")
    print(f"Top K Retrieval: {settings.rag.top_k_retrieval}")
    print(f"Log Level: {settings.logging.log_level}")

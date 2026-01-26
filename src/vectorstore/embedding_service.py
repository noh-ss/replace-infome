"""
임베딩 서비스
Ollama를 사용한 텍스트 임베딩 생성
"""

import time
from typing import List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from src.utils.logger import get_vectorstore_logger


logger = get_vectorstore_logger()


class EmbeddingService:
    """Ollama 기반 임베딩 생성 서비스"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: int = 32
    ):
        """
        EmbeddingService 초기화

        Args:
            base_url: Ollama API 기본 URL
            model: 임베딩 모델 이름
            batch_size: 배치 크기
        """
        self.base_url = base_url or settings.ollama.base_url
        self.model = model or settings.ollama.embedding_model
        self.batch_size = batch_size

        # API 엔드포인트
        self.embed_endpoint = f"{self.base_url}/api/embeddings"

        logger.info(
            f"EmbeddingService initialized: model={self.model}, "
            f"base_url={self.base_url}, batch_size={self.batch_size}"
        )

        # Ollama 연결 확인
        self._check_connection()

    def _check_connection(self) -> bool:
        """
        Ollama 서버 연결 확인

        Returns:
            연결 성공 여부
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("Successfully connected to Ollama server")
                return True
            else:
                logger.warning(f"Ollama server responded with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to Ollama server: {str(e)}")
            logger.warning("Make sure Ollama is running: 'ollama serve'")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def embed_text(self, text: str) -> List[float]:
        """
        단일 텍스트 임베딩 생성

        Args:
            text: 임베딩할 텍스트

        Returns:
            임베딩 벡터

        Raises:
            Exception: 임베딩 생성 실패
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []

        try:
            # Ollama API 호출
            payload = {
                "model": self.model,
                "prompt": text
            }

            response = requests.post(
                self.embed_endpoint,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                embedding = result.get("embedding", [])

                if not embedding:
                    logger.error("No embedding returned from Ollama")
                    raise Exception("Empty embedding returned")

                logger.debug(f"Generated embedding with dimension {len(embedding)}")
                return embedding

            else:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.exceptions.Timeout:
            logger.error("Ollama API timeout")
            raise Exception("Embedding request timeout")

        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama API request failed: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error during embedding: {str(e)}")
            raise

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        배치 텍스트 임베딩 생성

        Args:
            texts: 임베딩할 텍스트 목록

        Returns:
            임베딩 벡터 목록
        """
        if not texts:
            return []

        embeddings = []
        total_texts = len(texts)

        logger.info(f"Generating embeddings for {total_texts} texts...")

        for i in range(0, total_texts, self.batch_size):
            batch = texts[i:i + self.batch_size]
            batch_start = i + 1
            batch_end = min(i + self.batch_size, total_texts)

            logger.info(f"Processing batch {batch_start}-{batch_end}/{total_texts}")

            batch_embeddings = []
            for text in batch:
                try:
                    embedding = self.embed_text(text)
                    batch_embeddings.append(embedding)

                    # API 속도 제한 고려
                    time.sleep(0.1)

                except Exception as e:
                    logger.error(f"Failed to embed text (skipping): {str(e)[:100]}")
                    # 실패한 경우 빈 임베딩 추가 (또는 None)
                    batch_embeddings.append([])

            embeddings.extend(batch_embeddings)

        logger.info(f"Successfully generated {len(embeddings)} embeddings")

        return embeddings

    def get_embedding_dimension(self) -> int:
        """
        임베딩 차원 수 반환

        Returns:
            임베딩 벡터 차원
        """
        try:
            # 샘플 텍스트로 임베딩 생성
            sample_embedding = self.embed_text("test")
            dimension = len(sample_embedding)

            logger.info(f"Embedding dimension: {dimension}")
            return dimension

        except Exception as e:
            logger.error(f"Failed to get embedding dimension: {str(e)}")
            # nomic-embed-text 기본 차원
            return 768

    def check_model_availability(self) -> bool:
        """
        임베딩 모델 사용 가능 여부 확인

        Returns:
            사용 가능 여부
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)

            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]

                if self.model in model_names or any(self.model in name for name in model_names):
                    logger.info(f"Model '{self.model}' is available")
                    return True
                else:
                    logger.warning(f"Model '{self.model}' not found in available models")
                    logger.info(f"Available models: {model_names}")
                    logger.info(f"Please run: ollama pull {self.model}")
                    return False

            return False

        except Exception as e:
            logger.error(f"Failed to check model availability: {str(e)}")
            return False


if __name__ == "__main__":
    # EmbeddingService 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    print("=== EmbeddingService 테스트 ===\n")

    # 서비스 초기화
    service = EmbeddingService()

    # 모델 확인
    print("1. 모델 가용성 확인")
    is_available = service.check_model_availability()
    print(f"모델 사용 가능: {is_available}\n")

    if not is_available:
        print("⚠️  Ollama 모델을 먼저 다운로드하세요:")
        print(f"   ollama pull {service.model}")
        sys.exit(1)

    # 임베딩 차원 확인
    print("2. 임베딩 차원 확인")
    dimension = service.get_embedding_dimension()
    print(f"임베딩 차원: {dimension}\n")

    # 단일 텍스트 임베딩
    print("3. 단일 텍스트 임베딩")
    test_text = "경상국립대학교는 대한민국의 국립대학교입니다."
    embedding = service.embed_text(test_text)
    print(f"텍스트: {test_text}")
    print(f"임베딩 차원: {len(embedding)}")
    print(f"임베딩 샘플 (처음 10개): {embedding[:10]}\n")

    # 배치 임베딩
    print("4. 배치 텍스트 임베딩")
    test_texts = [
        "경상국립대학교 입학 안내",
        "도서관 이용 시간",
        "장학금 신청 방법",
        "캠퍼스 위치 안내",
        "교내 식당 운영 시간"
    ]

    batch_embeddings = service.embed_batch(test_texts)
    print(f"배치 크기: {len(test_texts)}")
    print(f"생성된 임베딩: {len(batch_embeddings)}")

    for i, (text, emb) in enumerate(zip(test_texts, batch_embeddings), 1):
        print(f"  {i}. {text}: {len(emb)} 차원")

    print("\n✅ 테스트 완료!")

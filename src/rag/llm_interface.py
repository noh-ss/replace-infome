"""
LLM 인터페이스
Ollama를 사용한 텍스트 생성
"""

from typing import Optional, Generator
import requests
import json

from config.settings import settings
from src.utils.logger import get_rag_logger


logger = get_rag_logger()


class LLMInterface:
    """Ollama LLM 인터페이스"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        LLMInterface 초기화

        Args:
            base_url: Ollama API 기본 URL
            model: LLM 모델 이름
        """
        self.base_url = base_url or settings.ollama.base_url
        self.model = model or settings.ollama.llm_model

        # API 엔드포인트
        self.generate_endpoint = f"{self.base_url}/api/generate"
        self.chat_endpoint = f"{self.base_url}/api/chat"

        # 프롬프트 템플릿
        self.system_prompt = """당신은 경상국립대학교(GNU) 관련 질문에 답하는 전문 상담원입니다.

제공된 정보를 바탕으로 사용자 질문에 정확하고 친절하게 답변하세요.

답변 지침:
- 제공된 정보만을 사용하여 답변하세요
- 정보가 불충분하면 솔직하게 알려주세요
- 출처를 명시하세요
- 친절하고 전문적인 톤을 유지하세요
- 답변은 한국어로 작성하세요"""

        logger.info(f"LLMInterface initialized: model={self.model}, base_url={self.base_url}")

        # 연결 확인
        self._check_connection()

    def _check_connection(self) -> bool:
        """Ollama 서버 연결 확인"""
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
            return False

    def generate(
        self,
        prompt: str,
        context: str = "",
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        텍스트 생성

        Args:
            prompt: 사용자 질문
            context: 참조할 컨텍스트
            stream: 스트리밍 여부
            temperature: 온도 (0.0 ~ 1.0)
            max_tokens: 최대 토큰 수

        Returns:
            생성된 텍스트
        """
        # 전체 프롬프트 구성
        full_prompt = self._build_prompt(prompt, context)

        logger.info(f"Generating response for prompt: '{prompt[:100]}...'")
        logger.debug(f"Full prompt length: {len(full_prompt)} characters")

        try:
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=120,
                stream=stream
            )

            if response.status_code == 200:
                if stream:
                    return self._handle_stream_response(response)
                else:
                    result = response.json()
                    generated_text = result.get("response", "")
                    logger.info(f"Generated {len(generated_text)} characters")
                    return generated_text
            else:
                error_msg = f"Ollama API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {error_msg}"

        except requests.exceptions.Timeout:
            logger.error("LLM request timeout")
            return "죄송합니다. 응답 생성 시간이 초과되었습니다."

        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}")
            return f"죄송합니다. 응답 생성 중 오류가 발생했습니다: {str(e)}"

    def generate_stream(
        self,
        prompt: str,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """
        스트리밍 텍스트 생성

        Args:
            prompt: 사용자 질문
            context: 참조할 컨텍스트
            temperature: 온도
            max_tokens: 최대 토큰 수

        Yields:
            생성된 텍스트 청크
        """
        full_prompt = self._build_prompt(prompt, context)

        logger.info(f"Generating streaming response for prompt: '{prompt[:100]}...'")

        try:
            payload = {
                "model": self.model,
                "prompt": full_prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            response = requests.post(
                self.generate_endpoint,
                json=payload,
                timeout=120,
                stream=True
            )

            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line)
                            text = chunk.get("response", "")
                            if text:
                                yield text

                            # 완료 확인
                            if chunk.get("done", False):
                                break

                        except json.JSONDecodeError:
                            continue

                logger.info("Streaming generation completed")

            else:
                error_msg = f"Ollama API error: {response.status_code}"
                logger.error(error_msg)
                yield f"죄송합니다. 응답 생성 중 오류가 발생했습니다."

        except Exception as e:
            logger.error(f"Streaming generation failed: {str(e)}")
            yield f"죄송합니다. 응답 생성 중 오류가 발생했습니다."

    def _build_prompt(self, question: str, context: str = "") -> str:
        """
        프롬프트 구성

        Args:
            question: 사용자 질문
            context: 참조 컨텍스트

        Returns:
            전체 프롬프트
        """
        prompt_parts = [self.system_prompt]

        if context:
            prompt_parts.append(f"\n[참조 정보]\n{context}")

        prompt_parts.append(f"\n[질문]\n{question}")

        prompt_parts.append("\n[답변]")

        return "\n".join(prompt_parts)

    def _handle_stream_response(self, response) -> str:
        """스트리밍 응답 처리"""
        full_response = []

        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    text = chunk.get("response", "")
                    if text:
                        full_response.append(text)

                    if chunk.get("done", False):
                        break

                except json.JSONDecodeError:
                    continue

        return "".join(full_response)


if __name__ == "__main__":
    # LLMInterface 테스트
    import sys
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    print("=== LLMInterface 테스트 ===\n")

    # LLM 초기화
    llm = LLMInterface()

    # 테스트 1: 컨텍스트 없이 생성
    print("1. 컨텍스트 없이 질문")
    print("-" * 80)

    question1 = "경상국립대학교에 대해 알려주세요."
    response1 = llm.generate(question1)

    print(f"질문: {question1}")
    print(f"답변: {response1}\n")

    # 테스트 2: 컨텍스트와 함께 생성
    print("2. 컨텍스트와 함께 질문")
    print("-" * 80)

    context = """
    [문서 1]
    제목: 경상국립대학교 소개
    출처: https://gnu.ac.kr/about
    내용: 경상국립대학교는 1948년에 설립된 대한민국의 국립대학교입니다.
    경상남도 진주시에 본캠퍼스가 있으며, 11개 단과대학과 7개 대학원을 운영하고 있습니다.

    [문서 2]
    제목: 입학 안내
    출처: https://gnu.ac.kr/admission
    내용: 경상국립대학교는 수시모집과 정시모집을 통해 신입생을 선발합니다.
    자세한 모집요강은 입학처 홈페이지에서 확인할 수 있습니다.
    """

    question2 = "경상국립대학교는 어디에 있나요?"
    response2 = llm.generate(question2, context=context)

    print(f"질문: {question2}")
    print(f"답변: {response2}\n")

    # 테스트 3: 스트리밍 생성
    print("3. 스트리밍 생성 테스트")
    print("-" * 80)

    question3 = "경상국립대학교 입학 전형에 대해 설명해주세요."

    print(f"질문: {question3}")
    print("답변: ", end="", flush=True)

    for chunk in llm.generate_stream(question3, context=context):
        print(chunk, end="", flush=True)

    print("\n\n✅ 테스트 완료!")

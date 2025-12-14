"""
Gemini API 호출 래퍼 서비스
OpenRouter API를 사용하여 Gemini 2.0 Flash Experimental 모델 호출
"""

import httpx
from typing import Optional, Dict, Any
import json
import logging
from app.core.config import settings
try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover - 방어적 처리
    repair_json = None

logger = logging.getLogger(__name__)


class GeminiService:
    """OpenRouter API를 통한 AI 모델 통신 서비스"""

    def __init__(self, model_name: Optional[str] = None):
        """
        OpenRouter API 초기화
        
        Args:
            model_name: 사용할 모델명 (None이면 기본 모델 사용)
        """
        if not settings.OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY가 설정되지 않았습니다.")
            self.is_configured = False
            self.api_url = None
            self.headers = None
            self.model_name = None
        else:
            # OpenRouter API 설정
            self.api_url = "https://openrouter.ai/api/v1/chat/completions"
            self.headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            # 모델 설정 (파라미터로 전달되지 않으면 퀴즈 모델을 기본값으로)
            self.model_name = model_name or settings.OPENROUTER_QUIZ_MODEL
            self.is_configured = True
            logger.info(f"OpenRouter API 초기화 완료 (모델: {self.model_name})")

    async def generate_content(
        self,
        prompt: str,
        temperature: float = 0.4,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        OpenRouter API를 사용하여 텍스트 생성

        Args:
            prompt: 생성할 내용에 대한 프롬프트
            temperature: 생성 다양성 (0.0-1.0, 낮을수록 일관적)
            max_tokens: 최대 토큰 수 (None이면 기본값 사용)

        Returns:
            생성된 텍스트

        Raises:
            ValueError: API 키가 설정되지 않은 경우
            Exception: API 호출 실패 시
        """
        if not self.is_configured:
            raise ValueError(
                "OpenRouter API 키가 설정되지 않았습니다. "
                "OPENROUTER_API_KEY 환경 변수를 확인하세요."
            )

        try:
            # OpenRouter API 요청 데이터 구성
            request_data = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature,
            }
            
            # max_tokens 옵션 추가
            if max_tokens is not None:
                request_data["max_tokens"] = max_tokens

            logger.info(
                f"OpenRouter API 호출 시작 (모델: {self.model_name}, "
                f"프롬프트 길이: {len(prompt)} 문자, temperature: {temperature})"
            )

            # 비동기 HTTP 요청
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=self.headers,
                    json=request_data
                )

                # HTTP 상태 코드 확인
                if response.status_code != 200:
                    error_text = response.text
                    logger.error(
                        f"OpenRouter API 호출 실패 (HTTP {response.status_code}): {error_text}"
                    )
                    raise Exception(
                        f"OpenRouter API 호출 실패 (HTTP {response.status_code}): {error_text}"
                    )

                # 응답 파싱
                response_data = response.json()
                
                # 응답 구조 로깅
                logger.info(f"응답 키: {list(response_data.keys())}")
                
                # choices에서 텍스트 추출
                if "choices" not in response_data or not response_data["choices"]:
                    logger.error(f"OpenRouter API 응답에 choices가 없습니다: {response_data}")
                    raise Exception("OpenRouter API에서 빈 응답을 받았습니다.")

                choice = response_data["choices"][0]
                
                # finish_reason 확인
                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    logger.info(f"finish_reason: {finish_reason}")
                    if finish_reason == "length":
                        logger.warning(
                            "⚠️ 응답이 max_tokens 제한에 도달하여 잘렸습니다. "
                            "max_tokens를 늘려주세요."
                        )

                # 메시지 내용 추출
                message = choice.get("message", {})
                content = message.get("content", "")
                
                if not content:
                    logger.error(f"OpenRouter API 응답 메시지가 비어있습니다: {response_data}")
                    raise Exception("OpenRouter API에서 빈 메시지를 받았습니다.")

                logger.info(
                    f"OpenRouter API 호출 성공 (응답 길이: {len(content)} 문자)"
                )
                
                return content

        except httpx.HTTPError as e:
            logger.error(f"HTTP 요청 실패: {str(e)}")
            raise Exception(f"OpenRouter API 호출 중 네트워크 오류 발생: {str(e)}")
        except Exception as e:
            logger.error(f"OpenRouter API 호출 실패: {str(e)}")
            raise Exception(f"OpenRouter API 호출 중 오류 발생: {str(e)}")

    async def generate_json(
        self,
        prompt: str,
        temperature: float = 0.4,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Gemini API를 사용하여 JSON 형식 응답 생성

        Args:
            prompt: 생성할 내용에 대한 프롬프트 (JSON 형식 요청 포함)
            temperature: 생성 다양성
            max_tokens: 최대 토큰 수

        Returns:
            파싱된 JSON 딕셔너리

        Raises:
            ValueError: JSON 파싱 실패 시
        """
        response_text = await self.generate_content(prompt, temperature, max_tokens)

        try:
            # 응답에서 JSON 부분만 추출 (마크다운 코드 블록 제거)
            cleaned_response = response_text.strip()

            # ```json ... ``` 형식 처리
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]  # "```json" 제거
            elif cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]  # "```" 제거

            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]  # "```" 제거

            cleaned_response = cleaned_response.strip()

            # JSON 파싱
            parsed_json = json.loads(cleaned_response)
            logger.info("JSON 응답 파싱 성공")
            return parsed_json

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {str(e)}")
            logger.error(f"원본 응답 (처음 1000자):\n{response_text[:1000]}")
            logger.error(f"원본 응답 (끝 500자):\n{response_text[-500:]}")  # 끝부분도 확인

            # json_repair를 활용한 복구 시도
            if repair_json is not None:
                try:
                    logger.info("json_repair로 복구 시도 중...")
                    repaired = repair_json(cleaned_response)
                    logger.info(f"복구된 JSON (처음 500자):\n{repaired[:500]}")
                    parsed_json = json.loads(repaired)
                    logger.info("json_repair를 사용해 JSON 응답 복구 성공")
                    return parsed_json
                except Exception as repair_error:
                    logger.error(f"json_repair 복구 실패: {type(repair_error).__name__}: {repair_error}")
                    # NameError 같은 경우 원본 응답에 문제가 있음
                    if isinstance(repair_error, NameError):
                        logger.error(f"⚠️ json_repair가 변수를 평가하려고 시도했습니다. 원본 JSON에 변수가 포함되어 있을 가능성이 높습니다.")
            else:
                logger.error("json_repair 패키지가 설치되어 있지 않아 응답 복구를 건너뜁니다.")

            raise ValueError(f"Gemini API 응답을 JSON으로 파싱할 수 없습니다: {str(e)}")


# 싱글톤 인스턴스 (기본 모델용)
_gemini_service: Optional[GeminiService] = None


def get_gemini_service(model_name: Optional[str] = None) -> GeminiService:
    """
    GeminiService 인스턴스 반환
    
    Args:
        model_name: 사용할 모델명 (None이면 싱글톤 기본 인스턴스 반환)
        
    Returns:
        GeminiService 인스턴스
        
    Note:
        model_name이 지정되면 새 인스턴스를 생성하여 반환합니다.
        model_name이 None이면 싱글톤 인스턴스를 반환합니다.
    """
    if model_name is not None:
        # 특정 모델을 위한 새 인스턴스 생성
        return GeminiService(model_name=model_name)
    
    # 기본 싱글톤 인스턴스
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service

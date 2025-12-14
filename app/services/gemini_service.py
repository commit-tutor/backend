"""
Gemini API 호출 래퍼 서비스
Google GenAI Python SDK를 사용하여 텍스트 생성 요청 처리
"""

from google import genai
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
    """Gemini API 통신을 담당하는 서비스 클래스"""

    def __init__(self):
        """Gemini API 초기화"""
        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY가 설정되지 않았습니다.")
            self.is_configured = False
            self.client = None
        else:
            # Google GenAI Client 초기화
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            # Gemma 3 27B IT - Google의 오픈소스 instruction-tuned 모델
            self.model_name = 'gemma-3-27b-it'
            self.is_configured = True
            logger.info("Gemini API가 성공적으로 초기화되었습니다.")

    async def generate_content(
        self,
        prompt: str,
        temperature: float = 0.4,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Gemini API를 사용하여 텍스트 생성

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
        if not self.is_configured or not self.client:
            raise ValueError("Gemini API 키가 설정되지 않았습니다. GEMINI_API_KEY 환경 변수를 확인하세요.")

        try:
            # GenerateContentConfig 설정
            config = genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # 비동기 클라이언트로 content 생성
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # 응답 구조 디버깅
            logger.info(f"응답 객체 타입: {type(response)}")
            logger.info(f"응답 candidates 개수: {len(response.candidates) if hasattr(response, 'candidates') else 'N/A'}")

            # finish_reason 확인
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = response.candidates[0].finish_reason if hasattr(response.candidates[0], 'finish_reason') else None
                logger.info(f"finish_reason: {finish_reason}")

                # MAX_TOKENS 경고
                if finish_reason and 'MAX_TOKENS' in str(finish_reason):
                    logger.warning(f"⚠️ 응답이 max_tokens 제한에 도달하여 잘렸습니다. max_tokens를 늘려주세요.")

            # 응답 텍스트 추출
            if hasattr(response, 'text') and response.text:
                logger.info(f"Gemini API 호출 성공 (프롬프트 길이: {len(prompt)} 문자, 응답 길이: {len(response.text)} 문자)")
                return response.text

            # 대체 방법: candidates에서 직접 추출
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    text = candidate.content.parts[0].text
                    logger.info(f"Gemini API 호출 성공 (candidates 방식, 응답 길이: {len(text)} 문자)")
                    return text

            # 모든 방법 실패
            logger.error(f"Gemini API 응답이 비어있습니다. 응답 구조: {response}")
            logger.error(f"response.candidates: {response.candidates if hasattr(response, 'candidates') else 'N/A'}")
            if hasattr(response, 'prompt_feedback'):
                logger.error(f"prompt_feedback: {response.prompt_feedback}")

            # finish_reason이 MAX_TOKENS인 경우 더 명확한 에러 메시지
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = response.candidates[0].finish_reason if hasattr(response.candidates[0], 'finish_reason') else None
                if finish_reason and 'MAX_TOKENS' in str(finish_reason):
                    raise Exception(f"Gemini API 응답이 max_tokens 제한({max_tokens})에 도달하여 잘렸습니다. max_tokens 값을 늘려주세요.")

            raise Exception("Gemini API에서 빈 응답을 받았습니다.")

        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {str(e)}")
            raise Exception(f"Gemini API 호출 중 오류 발생: {str(e)}")

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


# 싱글톤 인스턴스
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """GeminiService 싱글톤 인스턴스 반환"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service

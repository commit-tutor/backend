"""
코드 분석 서비스
커밋 diff 데이터를 기반으로 Gemini API를 사용하여 AI 코드 리뷰 생성
"""

from typing import List, Optional
import logging
import re

from app.services.gemini_service import get_gemini_service
from app.schemas.analysis import AIAnalysisResponse, CodeQuality, CommitDetailResponse

logger = logging.getLogger(__name__)


class CodeAnalyzer:
    """코드 분석 및 리뷰 생성을 담당하는 서비스 클래스"""

    def __init__(self):
        self.gemini_service = get_gemini_service()

    def _detect_language(self, commit: CommitDetailResponse) -> str:
        """
        커밋에서 주요 프로그래밍 언어 감지

        Args:
            commit: 커밋 상세 정보

        Returns:
            감지된 언어 (예: Python, JavaScript, TypeScript 등)
        """
        language_extensions = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript React",
            ".jsx": "JavaScript React",
            ".java": "Java",
            ".go": "Go",
            ".rs": "Rust",
            ".cpp": "C++",
            ".c": "C",
            ".rb": "Ruby",
            ".php": "PHP",
            ".swift": "Swift",
            ".kt": "Kotlin",
        }

        language_counts = {}
        for file in commit.files:
            for ext, lang in language_extensions.items():
                if file.filename.endswith(ext):
                    language_counts[lang] = language_counts.get(lang, 0) + 1

        if language_counts:
            # 가장 많이 사용된 언어 반환
            return max(language_counts, key=language_counts.get)

        return "Unknown"

    def _build_analysis_prompt(
        self,
        commit: CommitDetailResponse,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        코드 분석을 위한 프롬프트 구성

        Args:
            commit: 커밋 상세 정보
            focus_areas: 집중 분석 영역 (선택)

        Returns:
            구성된 프롬프트 문자열
        """
        language = self._detect_language(commit)

        # 파일 변경 정보 구성
        files_info = []
        for file in commit.files[:10]:  # 최대 10개 파일
            file_info = f"""
파일: {file.filename} ({file.status})
변경: +{file.additions} -{file.deletions}
"""
            if file.patch:
                # diff를 적절한 길이로 제한
                patch_preview = file.patch[:800] + ("..." if len(file.patch) > 800 else "")
                file_info += f"Diff:\n{patch_preview}"

            files_info.append(file_info)

        files_text = "\n\n".join(files_info)

        # 집중 분석 영역 설정
        focus_text = ""
        if focus_areas:
            focus_text = f"\n\n**특별히 집중할 분석 영역:** {', '.join(focus_areas)}"

        # Few-shot 예시
        example_response = """
{
  "summary": "JWT 토큰 생성 방식을 커스텀 함수에서 표준 라이브러리로 변경하여 보안성과 호환성을 강화했습니다.",
  "quality": {
    "readability": 85,
    "performance": 90,
    "security": 70
  },
  "suggestions": [
    "SECRET_KEY를 환경 변수로 분리하여 하드코딩을 방지하세요.",
    "토큰 만료 시간(expiresIn)을 설정하여 보안을 강화하세요.",
    "에러 핸들링을 추가하여 토큰 생성 실패 시 적절히 처리하세요."
  ],
  "potentialBugs": [
    "SECRET_KEY가 코드에 하드코딩되어 있어 보안 위험이 있습니다.",
    "payload 검증 로직이 없어 잘못된 데이터로 토큰이 생성될 수 있습니다."
  ]
}
"""

        # 최종 프롬프트
        prompt = f"""당신은 경력 10년의 시니어 코드 리뷰어입니다.
아래 커밋 변경사항을 전문적으로 분석하고 건설적인 피드백을 제공해주세요.

**커밋 정보:**
SHA: {commit.sha[:7]}
메시지: {commit.message}
작성자: {commit.author}
날짜: {commit.date}
주요 언어: {language}
전체 변경: +{commit.additions} -{commit.deletions} ({commit.filesChanged}개 파일)

**변경된 파일:**
{files_text}
{focus_text}

**분석 요구사항:**

1. **요약 (summary):**
   - 이 커밋의 핵심 변경사항을 1-2문장으로 요약하세요
   - 변경의 목적과 영향 범위를 명확히 하세요

2. **코드 품질 점수 (quality):**
   - readability (가독성): 0-100점
     * 변수/함수 이름의 명확성
     * 코드 구조와 복잡도
     * 주석과 문서화 품질

   - performance (성능): 0-100점
     * 알고리즘 효율성
     * 불필요한 연산 여부
     * 메모리 사용 최적화

   - security (보안): 0-100점
     * OWASP Top 10 기준 검토
     * 입력 검증 및 에러 핸들링
     * 민감 정보 노출 여부

3. **개선 제안 (suggestions):**
   - 3-5개의 구체적이고 실행 가능한 제안
   - 우선순위가 높은 것부터 나열
   - {language} 및 관련 프레임워크의 베스트 프랙티스 적용

4. **잠재적 버그 (potentialBugs):**
   - 코드에서 발견된 잠재적 문제점 나열
   - null/undefined 체크 누락
   - 에러 핸들링 부재
   - 타입 불일치 등
   - 문제가 없으면 빈 배열 반환

**출력 형식:**
반드시 아래 JSON 형식으로만 응답하세요. 추가 설명은 포함하지 마세요.

{example_response}

**주의사항:**
- 점수는 반드시 0-100 사이의 정수여야 합니다
- 비판적이되 건설적인 톤을 유지하세요
- 실제 코드 변경사항에 기반한 분석만 제공하세요
- {language}의 컨벤션과 베스트 프랙티스를 고려하세요

이제 위 커밋을 분석하여 JSON 형식으로 응답해주세요:"""

        return prompt

    def _validate_quality_scores(self, quality: dict) -> CodeQuality:
        """
        코드 품질 점수 검증 및 보정

        Args:
            quality: 원본 품질 점수 딕셔너리

        Returns:
            검증된 CodeQuality 객체
        """
        def clamp(value: int, min_val: int = 0, max_val: int = 100) -> int:
            """값을 min_val과 max_val 사이로 제한"""
            try:
                val = int(value)
                return max(min_val, min(max_val, val))
            except (ValueError, TypeError):
                logger.warning(f"잘못된 점수 값: {value}, 기본값 75 사용")
                return 75

        return CodeQuality(
            readability=clamp(quality.get("readability", 75)),
            performance=clamp(quality.get("performance", 75)),
            security=clamp(quality.get("security", 75))
        )

    async def analyze_commit(
        self,
        commit: CommitDetailResponse,
        focus_areas: Optional[List[str]] = None
    ) -> AIAnalysisResponse:
        """
        커밋 변경사항 분석 및 AI 리뷰 생성

        Args:
            commit: 커밋 상세 정보
            focus_areas: 집중 분석 영역 (예: ['security', 'performance'])

        Returns:
            AI 분석 결과

        Raises:
            ValueError: 분석 실패 시
        """
        try:
            logger.info(f"[CodeAnalyzer] 코드 분석 시작: {commit.sha[:7]} - {commit.message[:50]}")

            # 프롬프트 구성
            prompt = self._build_analysis_prompt(commit, focus_areas)
            logger.info(f"[CodeAnalyzer] ========== 생성된 프롬프트 ==========")
            logger.info(f"프롬프트 길이: {len(prompt)} 문자")
            logger.info(f"프롬프트 내용:\n{prompt[:1000]}...")  # 처음 1000자만
            logger.info(f"===========================================")

            # Gemini API 호출 (JSON 응답 요청)
            logger.info(f"[CodeAnalyzer] Gemini API 호출 중... (temperature=0.3, max_tokens=6000)")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.3,  # 일관성 있는 분석을 위해 낮은 temperature
                max_tokens=6000  # 충분한 토큰 확보 (JSON 잘림 방지)
            )

            logger.info(f"[CodeAnalyzer] ========== Gemini 응답 데이터 ==========")
            logger.info(f"응답 키: {list(response_data.keys())}")
            logger.info(f"응답 전체: {str(response_data)[:500]}...")
            logger.info(f"=================================================")

            # 필수 필드 검증
            required_fields = ["summary", "quality", "suggestions", "potentialBugs"]
            for field in required_fields:
                if field not in response_data:
                    raise ValueError(f"Gemini API 응답에 '{field}' 필드가 없습니다.")

            # 품질 점수 검증 및 보정
            quality = self._validate_quality_scores(response_data["quality"])

            # AIAnalysisResponse 객체 생성
            analysis = AIAnalysisResponse(
                summary=response_data["summary"],
                quality=quality,
                suggestions=response_data.get("suggestions", []),
                potentialBugs=response_data.get("potentialBugs", [])
            )

            logger.info(f"코드 분석 완료: {commit.sha[:7]}")
            logger.info(f"품질 점수 - 가독성: {quality.readability}, "
                       f"성능: {quality.performance}, 보안: {quality.security}")

            return analysis

        except Exception as e:
            logger.error(f"코드 분석 실패: {str(e)}")
            raise ValueError(f"코드 분석 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_code_analyzer = None


def get_code_analyzer() -> CodeAnalyzer:
    """CodeAnalyzer 싱글톤 인스턴스 반환"""
    global _code_analyzer
    if _code_analyzer is None:
        _code_analyzer = CodeAnalyzer()
    return _code_analyzer

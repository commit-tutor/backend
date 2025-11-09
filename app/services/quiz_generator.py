"""
퀴즈 생성 서비스
커밋 diff 데이터를 기반으로 Gemini API를 사용하여 학습용 퀴즈 생성
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import QuizQuestionResponse, QuizGenerationResponse
from app.schemas.analysis import CommitDetailResponse

logger = logging.getLogger(__name__)


class QuizGenerator:
    """퀴즈 생성을 담당하는 서비스 클래스"""

    def __init__(self):
        self.gemini_service = get_gemini_service()
        self._type_aliases = {
            "subjective": "short",
            "descriptive": "short",
            "open-ended": "short",
            "open_ended": "short",
            "short_answer": "short",
            "objective": "multiple",
            "multiple_choice": "multiple",
            "mcq": "multiple",
        }
        self._max_code_context_length = 800
        self._max_options = 4

    def _normalize_question_data(self, raw_data: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
        """
        Gemini 응답을 QuizQuestionResponse가 기대하는 형태로 정규화
        비정상 데이터는 None을 반환하여 호출부에서 건너뛸 수 있게 함
        """
        if not isinstance(raw_data, dict):
            logger.warning(f"질문 {idx + 1} 데이터가 dict가 아님: {type(raw_data)}, 건너뜀")
            return None

        normalized = dict(raw_data)

        # 타입 매핑 처리
        q_type = str(normalized.get("type", "")).strip().lower()
        if not q_type:
            q_type = "multiple" if normalized.get("options") else "short"
        q_type = self._type_aliases.get(q_type, q_type)

        if q_type not in {"multiple", "short"}:
            logger.warning(f"질문 {idx + 1} 지원하지 않는 타입({q_type}) - 건너뜀")
            return None

        normalized["type"] = q_type

        # codeContext 길이 제한
        code_context = normalized.get("codeContext")
        if code_context is not None:
            code_context = str(code_context)
            if len(code_context) > self._max_code_context_length:
                code_context = code_context[: self._max_code_context_length] + "..."
            normalized["codeContext"] = code_context

        # 설명 필드 정리
        if normalized.get("explanation") is not None:
            normalized["explanation"] = str(normalized["explanation"]).strip()

        # 질문 본문 정리
        if normalized.get("question") is not None:
            normalized["question"] = str(normalized["question"]).strip()

        if q_type == "multiple":
            options = normalized.get("options") or []
            if not isinstance(options, list):
                logger.warning(f"질문 {idx + 1} 옵션 형식 오류 - 건너뜀")
                return None

            # 문자열화 + 최대 4개로 제한 (프롬프트 길이 절약)
            cleaned_options: List[str] = []
            for option in options:
                if option is None:
                    continue
                text = str(option).strip()
                if text:
                    cleaned_options.append(text)
                if len(cleaned_options) >= self._max_options:
                    break

            if len(cleaned_options) < 2:
                logger.warning(f"질문 {idx + 1} 옵션 부족 - 건너뜀")
                return None

            normalized["options"] = cleaned_options

            correct = normalized.get("correctAnswer", normalized.get("answer"))
            if correct is None and isinstance(normalized.get("explanation"), str):
                # "정답: ..." 형태가 설명에 포함되어 있는 경우 추출
                explanation = normalized["explanation"]
                if "정답:" in explanation:
                    correct = explanation.split("정답:", 1)[1].strip().split("\n")[0]

            if isinstance(correct, str):
                stripped = correct.strip()
                if stripped.isdigit():
                    correct_idx = int(stripped)
                else:
                    correct_idx = next(
                        (i for i, opt in enumerate(cleaned_options) if stripped.lower() == opt.lower()),
                        None,
                    )
                    if correct_idx is None and stripped.startswith("option"):
                        # "option 1" 형태 대응
                        digits = "".join(ch for ch in stripped if ch.isdigit())
                        correct_idx = int(digits) if digits else None
                correct = correct_idx
            elif isinstance(correct, bool):
                correct = int(correct)

            if not isinstance(correct, int):
                logger.warning(f"질문 {idx + 1} 객관식 정답 형식 오류 - 건너뜀")
                return None

            if correct < 0 or correct >= len(cleaned_options):
                logger.warning(f"질문 {idx + 1} 객관식 정답 인덱스 범위 초과 - 건너뜀")
                return None

            normalized["correctAnswer"] = correct

        else:  # short form
            answer = normalized.get("correctAnswer")
            answer_candidates = [
                answer,
                normalized.get("answer"),
                normalized.get("shortAnswer"),
                normalized.get("expectedAnswer"),
            ]

            answer_text: Optional[str] = None
            for candidate in answer_candidates:
                if candidate is None:
                    continue
                if isinstance(candidate, list) and candidate:
                    candidate = candidate[0]
                if candidate is None:
                    continue
                answer_text = str(candidate).strip()
                if answer_text:
                    break

            if not answer_text and isinstance(normalized.get("explanation"), str):
                explanation = normalized["explanation"].split("\n")[0]
                answer_text = explanation.strip()

            if not answer_text:
                logger.warning(f"질문 {idx + 1} 주관식 정답 누락 - 건너뜀")
                return None

            normalized["correctAnswer"] = answer_text

        return normalized

    def _build_quiz_prompt(
        self,
        commits: List[CommitDetailResponse],
        question_count: int,
        difficulty: str
    ) -> str:
        """
        퀴즈 생성을 위한 프롬프트 구성

        Args:
            commits: 커밋 상세 정보 목록
            question_count: 생성할 퀴즈 개수
            difficulty: 난이도 (easy, medium, hard)

        Returns:
            구성된 프롬프트 문자열
        """
        # 난이도별 설명
        difficulty_guide = {
            "easy": "기본적인 코드 이해와 개념 파악에 중점",
            "medium": "코드의 의도, 패턴, 베스트 프랙티스에 중점",
            "hard": "심화된 분석, 최적화, 잠재적 이슈 발견에 중점"
        }

        # 커밋 정보 요약
        commits_summary = []
        for commit in commits:
            commit_info = f"""
커밋 SHA: {commit.sha[:7]}
메시지: {commit.message}
변경 통계: +{commit.additions} -{commit.deletions} ({commit.filesChanged}개 파일)

변경된 파일:
"""
            for file in commit.files[:5]:  # 최대 5개 파일만 포함
                commit_info += f"\n파일: {file.filename} ({file.status})"
                commit_info += f"\n  +{file.additions} -{file.deletions}"
                if file.patch:
                    # diff를 적절한 길이로 제한
                    patch_preview = file.patch[:500] + ("..." if len(file.patch) > 500 else "")
                    commit_info += f"\n  Diff:\n{patch_preview}"

            commits_summary.append(commit_info)

        commits_text = "\n\n---\n\n".join(commits_summary)

        # Few-shot 예시
        example_quiz = """
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple",
      "question": "이 코드 변경의 주요 목적은 무엇인가요?",
      "codeContext": "- const token = createToken(payload)\\n+ const token = jwt.sign(payload, secret)",
      "options": [
        "보안 강화를 위해 JWT 표준 라이브러리 사용",
        "코드 가독성 향상",
        "성능 최적화",
        "단순 리팩토링"
      ],
      "correctAnswer": 0,
      "explanation": "jwt.sign()을 사용하여 표준 JWT 토큰 생성 방식으로 변경했습니다. 이는 보안성과 호환성을 높이는 베스트 프랙티스입니다."
    }
  ]
}
"""

        # 최종 프롬프트
        prompt = f"""당신은 경력 10년의 시니어 개발자이자 코드 교육 전문가입니다.
아래 커밋 변경사항을 분석하여 개발자가 이 코드를 학습할 수 있는 고품질 퀴즈를 생성해주세요.

**커밋 정보:**
{commits_text}

**퀴즈 생성 요구사항:**
1. 총 {question_count}개의 퀴즈를 생성하세요
2. 난이도: {difficulty} ({difficulty_guide.get(difficulty, '')})
3. 문제 타입: 객관식 100% (주관식은 생성하지 마세요)
4. 각 문제는 실제 코드 변경사항에 기반해야 합니다
5. 객관식은 4개의 선택지를 제공하세요
6. 정답 설명은 구체적이고 교육적이어야 합니다

**퀴즈 주제 다양성:**
- 코드 이해 (변경의 목적, 의도)
- 버그 탐지 (잠재적 문제점)
- 베스트 프랙티스 (개선 방향)
- 기술 개념 (사용된 패턴, 라이브러리)
- 리팩토링 제안

**출력 형식:**
반드시 아래 JSON 형식으로만 응답하세요. 추가 설명은 포함하지 마세요.

{example_quiz}

**주의사항:**
- 모든 질문은 실제 커밋 내용과 직접적으로 연관되어야 합니다
- 정답 해설에는 "왜 그런지"를 명확히 설명하세요
- 너무 쉽거나 어려운 문제는 피하고 적절한 학습 효과를 주세요
- codeContext는 실제 diff 내용을 간결하게 포함하세요

이제 위 커밋들을 바탕으로 {question_count}개의 퀴즈를 JSON 형식으로 생성해주세요:"""

        return prompt

    async def generate_quiz(
        self,
        commits: List[CommitDetailResponse],
        question_count: int = 5,
        difficulty: str = "medium"
    ) -> QuizGenerationResponse:
        """
        커밋 정보를 기반으로 퀴즈 생성

        Args:
            commits: 커밋 상세 정보 목록
            question_count: 생성할 퀴즈 개수
            difficulty: 난이도 (easy, medium, hard)

        Returns:
            생성된 퀴즈 응답

        Raises:
            ValueError: 퀴즈 생성 실패 시
        """
        try:
            logger.info(f"[QuizGenerator] 퀴즈 생성 시작: {len(commits)}개 커밋, 난이도: {difficulty}")

            # 프롬프트 구성
            prompt = self._build_quiz_prompt(commits, question_count, difficulty)
            logger.info(f"[QuizGenerator] ========== 생성된 프롬프트 ==========")
            logger.info(f"프롬프트 길이: {len(prompt)} 문자")
            logger.info(f"프롬프트 내용:\n{prompt[:1000]}...")  # 처음 1000자만
            logger.info(f"===========================================")

            # Gemini API 호출 (JSON 응답 요청)
            logger.info(f"[QuizGenerator] Gemini API 호출 중... (temperature=0.4, max_tokens=8000)")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.4,  # 일관성을 위해 낮은 temperature
                max_tokens=8000  # 충분한 토큰 확보 (응답 잘림 방지)
            )

            logger.info(f"[QuizGenerator] ========== Gemini 응답 데이터 ==========")
            logger.info(f"응답 키: {list(response_data.keys())}")
            logger.info(f"응답 전체: {str(response_data)[:500]}...")
            logger.info(f"=================================================")

            # 응답 검증 및 파싱
            if "questions" not in response_data:
                raise ValueError("Gemini API 응답에 'questions' 필드가 없습니다.")

            questions_data = response_data["questions"]

            # QuizQuestionResponse 객체로 변환
            questions = []
            for idx, q_data in enumerate(questions_data):
                try:
                    # ID가 없으면 자동 생성
                    if "id" not in q_data:
                        q_data["id"] = f"q{idx + 1}"

                    normalized_data = self._normalize_question_data(q_data, idx)
                    if not normalized_data:
                        continue

                    question = QuizQuestionResponse(**normalized_data)
                    questions.append(question)
                except Exception as e:
                    logger.warning(f"질문 {idx + 1} 파싱 실패: {str(e)}, 건너뜀")
                    continue

            if not questions:
                raise ValueError("생성된 유효한 퀴즈가 없습니다.")

            logger.info(f"퀴즈 생성 완료: {len(questions)}개")

            return QuizGenerationResponse(
                questions=questions,
                metadata={
                    "totalCommits": len(commits),
                    "requestedCount": question_count,
                    "generatedCount": len(questions),
                    "difficulty": difficulty,
                    "generatedAt": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"퀴즈 생성 실패: {str(e)}")
            raise ValueError(f"퀴즈 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_quiz_generator = None


def get_quiz_generator() -> QuizGenerator:
    """QuizGenerator 싱글톤 인스턴스 반환"""
    global _quiz_generator
    if _quiz_generator is None:
        _quiz_generator = QuizGenerator()
    return _quiz_generator

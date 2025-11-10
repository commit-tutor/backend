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
        self._max_code_context_length = 800  # codeContext 필드에 저장할 최대 길이
        self._max_patch_preview_length = 1200  # 프롬프트에 포함할 diff 최대 길이 (늘림)
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
            "easy": "기본적인 CS 개념과 프로그래밍 원리 이해에 중점",
            "medium": "설계 패턴, 알고리즘, 데이터 구조의 실제 적용 이해",
            "hard": "성능 최적화, 시스템 설계, 보안 원칙 등 심화 개념 적용"
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
                    # diff를 충분히 제공 (학습자가 코드를 이해할 수 있도록)
                    patch_preview = file.patch[:self._max_patch_preview_length]
                    if len(file.patch) > self._max_patch_preview_length:
                        patch_preview += "\n... (중략) ..."
                    commit_info += f"\n  Diff:\n{patch_preview}"

            commits_summary.append(commit_info)

        commits_text = "\n\n---\n\n".join(commits_summary)

        # Few-shot 예시 (CS 원리 중심, 충분한 컨텍스트 제공)
        example_quiz = """
{
  "questions": [
    {
      "id": "q1",
      "type": "multiple",
      "question": "이 코드는 사용자 인증을 위해 JWT 기반의 stateless 방식으로 변경되었습니다. stateless 인증의 주요 장점은 무엇인가요?",
      "codeContext": "// 변경 전: 서버 세션 사용\\nfunction login(user) {\\n  session.set(user.id, user);\\n  return { sessionId: generateId() };\\n}\\n\\n// 변경 후: JWT 토큰 사용\\nfunction login(user) {\\n  const payload = { id: user.id, role: user.role };\\n  return { token: jwt.sign(payload, SECRET_KEY) };\\n}",
      "options": [
        "서버가 세션 상태를 저장하지 않아 수평 확장(horizontal scaling)이 용이하고, 서버 간 세션 동기화 문제가 없음",
        "클라이언트의 메모리 사용량을 대폭 줄일 수 있음",
        "네트워크 요청 시 암호화를 자동으로 수행하여 보안이 강화됨",
        "데이터베이스 조회 없이 인증하므로 DB 부하가 완전히 제거됨"
      ],
      "correctAnswer": 0,
      "explanation": "JWT는 토큰 자체에 사용자 정보를 담고 있어 서버가 세션 상태를 메모리나 DB에 저장할 필요가 없습니다(stateless). 이를 통해 여러 서버 인스턴스를 추가할 때 세션 공유 문제 없이 수평 확장이 가능하며, 로드밸런서를 통한 분산 처리가 자유롭습니다."
    },
    {
      "id": "q2",
      "type": "multiple",
      "question": "데이터베이스 쿼리 함수를 동기에서 비동기로 변경했습니다. async/await를 사용했을 때 Node.js의 이벤트 루프 관점에서 어떤 성능적 이점이 있나요?",
      "codeContext": "// 변경 전: 동기 방식 (blocking)\\nfunction getUsers() {\\n  const result = db.query('SELECT * FROM users');  // 쿼리 완료까지 대기\\n  return result;\\n}\\n\\n// 변경 후: 비동기 방식 (non-blocking)\\nasync function getUsers() {\\n  const result = await db.query('SELECT * FROM users');\\n  return result;\\n}",
      "options": [
        "I/O 대기 시간 동안 이벤트 루프가 다른 요청을 처리할 수 있어 동시성(concurrency)이 향상되고, 전체 처리량(throughput)이 증가함",
        "CPU 연산 속도가 빨라지고 메모리 사용량이 감소함",
        "데이터베이스 쿼리 자체의 실행 시간이 단축됨",
        "여러 쿼리를 병렬로 실행하여 멀티스레드처럼 동작함"
      ],
      "correctAnswer": 0,
      "explanation": "async/await는 Non-blocking I/O를 가능하게 합니다. DB 쿼리처럼 외부 I/O를 기다리는 동안 스레드를 차단하지 않고 이벤트 루프가 다른 요청을 처리할 수 있습니다. 이는 동시성(concurrency) 향상으로 이어지며, 싱글 스레드 환경에서도 높은 처리량을 달성할 수 있게 합니다."
    }
  ]
}
"""

        # 최종 프롬프트
        prompt = f"""당신은 컴퓨터 과학 교육 전문가입니다. 아래 커밋에서 **CS 원리와 개념**을 학습하는 퀴즈를 생성하세요.

# 커밋 정보
{commits_text}

# 요구사항
- 총 {question_count}개의 객관식 퀴즈 (4지선다)
- 난이도: {difficulty} - {difficulty_guide.get(difficulty, '')}
- 코드 세부사항이 아닌 **CS 원리**를 묻는 질문 (예: 시간복잡도, 동시성, 보안 원칙 등)

# CS 주제 카테고리 (골고루 분배)
자료구조, 알고리즘, 동시성/병렬성, 메모리 관리, 네트워크, 보안, 설계 패턴, 데이터베이스, 아키텍처

# JSON 출력 형식 (필수)
{example_quiz}

# 중요 규칙
1. **유효한 JSON만 출력** (마크다운, 주석 금지)
2. **codeContext는 충분히 제공**: 변경 전/후 코드를 모두 보여주되 최대 15줄 이내
3. **문자열 이스케이프**: \\n으로 줄바꿈, 따옴표는 \\" 처리
4. **변수 직접 참조 금지**: budgetRanges 같은 변수명을 그대로 쓰지 마세요
5. **오답도 교육적**: 흔한 오개념을 담아 학습 효과 증대
6. **설명은 깊이 있게**: 관련 CS 용어와 원리를 상세히 설명

이제 {question_count}개의 CS 원리 중심 퀴즈를 JSON으로 생성하세요:"""

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
            # 전체 응답을 JSON 형태로 예쁘게 출력 (디버깅용)
            import json as json_lib
            logger.info(f"응답 전체 (JSON):\n{json_lib.dumps(response_data, indent=2, ensure_ascii=False)[:2000]}...")
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

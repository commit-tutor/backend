"""
학습 세션 통합 서비스
퀴즈와 코드 리뷰를 단일 API 호출로 생성하여 토큰 절약
"""

from typing import List, Optional
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import QuizQuestionResponse, QuizGenerationResponse
from app.schemas.analysis import CommitDetailResponse

logger = logging.getLogger(__name__)


class LearningSessionService:
    """퀴즈와 코드 리뷰를 통합 생성하는 서비스"""

    def __init__(self):
        self.gemini_service = get_gemini_service()
        self._max_patch_preview_length = 1200

    def _build_unified_prompt(
        self,
        commits: List[CommitDetailResponse],
        question_count: int,
        difficulty: str,
        selected_topic: Optional[str] = None
    ) -> str:
        """통합 프롬프트 생성 (퀴즈 + 리뷰)"""

        difficulty_guide = {
            "easy": "기본적인 CS 개념과 프로그래밍 원리",
            "medium": "설계 패턴, 알고리즘, 데이터 구조의 실제 적용",
            "hard": "성능 최적화, 시스템 설계, 보안 원칙"
        }

        # 커밋 정보 요약
        commits_summary = []
        for commit in commits:
            commit_info = f"""
커밋 SHA: {commit.sha[:7]}
메시지: {commit.message}
작성자: {commit.author}
변경 통계: +{commit.additions} -{commit.deletions} ({commit.filesChanged}개 파일)

변경된 파일:"""
            for file in commit.files[:5]:
                commit_info += f"\n파일: {file.filename} ({file.status})"
                commit_info += f"\n  +{file.additions} -{file.deletions}"
                if file.patch:
                    patch_preview = file.patch[:self._max_patch_preview_length]
                    if len(file.patch) > self._max_patch_preview_length:
                        patch_preview += "\n... (중략) ..."
                    commit_info += f"\n  Diff:\n{patch_preview}"

            commits_summary.append(commit_info)

        commits_text = "\n\n---\n\n".join(commits_summary)

        # 퀴즈 예시
        example_output = """{
  "questions": [
    {
      "id": "q1",
      "type": "multiple",
      "question": "다음 코드에서 사용된 JWT 인증 방식의 주요 장점은 무엇인가요?",
      "codeContext": "function login(user) {\\n  const payload = { id: user.id, role: user.role };\\n  return { token: jwt.sign(payload, SECRET_KEY, { expiresIn: '1h' }) };\\n}",
      "options": [
        "서버가 세션 상태를 저장하지 않아 수평 확장(horizontal scaling)이 용이함",
        "클라이언트의 메모리 사용량을 줄일 수 있음",
        "네트워크 지연 시간이 단축됨",
        "데이터베이스 부하가 완전히 제거됨"
      ],
      "correctAnswer": 0,
      "explanation": "JWT는 토큰 자체에 정보를 담아 서버가 세션을 저장하지 않습니다(stateless). 여러 서버 인스턴스 간 세션 동기화 문제 없이 수평 확장이 가능합니다."
    }
  ]
}"""

        # 주제에 따른 퀴즈 스타일 변경
        if selected_topic:
            # 주제가 선택된 경우: 해당 주제의 전반적인 CS 지식 학습
            quiz_instruction = f"""
# 선택된 학습 주제
**{selected_topic}**

**퀴즈 생성 방식:**
커밋 코드는 참고만 하고, **"{selected_topic}"에 대한 전반적인 CS 지식**을 묻는 퀴즈를 생성하세요.

## 퀴즈 작성 원칙
1. **주제의 핵심 개념**을 다루세요 (커밋 코드에 국한되지 말 것)
2. **이론적 배경과 실무 적용**을 균형있게 다루세요
3. **일반적으로 알아야 할 지식**을 물으세요 (코드 세부사항 X)
4. codeContext는 개념 설명을 위한 **예시 코드** (커밋과 무관해도 됨)

## 좋은 예시 (주제 선택 시)
주제: "비동기 프로그래밍" →
질문: "JavaScript에서 Promise의 then() 체이닝이 콜백 헬(callback hell)을 해결하는 원리는?"
codeContext: "fetch('/api/user')\\n  .then(res => res.json())\\n  .then(data => console.log(data))"
설명: 주제의 핵심 개념 (Promise 체이닝)을 다루고, 일반적인 예시 코드 사용

주제: "REST API 설계" →
질문: "RESTful API에서 PUT과 PATCH의 차이점은?"
codeContext: "PUT /users/123 (전체 업데이트)\\nPATCH /users/123 (부분 업데이트)"
설명: 주제의 기본 개념을 다루고, HTTP 메서드 차이 설명

## 나쁜 예시 (주제 선택 시 금지)
❌ "이 커밋의 변수명이 바뀐 이유는?" (커밋에 집중)
❌ "다음 코드의 버그는?" (코드 세부사항)
❌ 커밋 코드를 그대로 codeContext로 사용 (일반적 예시를 써야 함)

# 퀴즈 요구사항
- {question_count}개의 객관식 (4지선다)
- 난이도: {difficulty_guide.get(difficulty, '')}
- **주제: {selected_topic}의 전반적인 개념**을 다루세요
- **codeContext: 개념 설명을 위한 일반적 예시 코드** (커밋과 무관해도 됨, 최대 8줄)
- 각 문제는 주제의 다른 측면을 다루세요 (중복 방지)
"""
        else:
            # 주제가 선택되지 않은 경우: 커밋 코드 기반 퀴즈
            quiz_instruction = f"""
# 퀴즈 작성 원칙
위 커밋의 **실제 코드**에서 사용된 기술/패턴을 보고, 그와 관련된 **CS 이론과 원리**를 물으세요.

## 좋은 예시
커밋에서 `async/await` 사용 발견 →
질문: "다음 코드에서 async/await의 동작 원리는?"
codeContext: "async function fetchData() {{\\n  const result = await db.query('SELECT * FROM users');\\n  return result;\\n}}"

커밋에서 `Array.map()` 사용 발견 →
질문: "다음 코드에서 map이 순수 함수로 간주되는 이유는?"
codeContext: "const doubled = items.map(x => x * 2);"

## 나쁜 예시 (금지)
❌ "이 변수명은 뭔가요?" (지엽적)
❌ codeContext를 임의로 만든 예시 (실제 커밋 코드를 사용해야 함)
❌ "변경 전/변경 후" 형식 (그냥 코드만 제시)

# 퀴즈 요구사항
- {question_count}개의 객관식 (4지선다)
- 난이도: {difficulty_guide.get(difficulty, '')}
- **실제 커밋 코드**에서 발견한 기술/개념과 **관련된 CS 원리**를 물으세요
- **codeContext: 위 커밋의 실제 코드 조각** (해당 개념을 보여주는 부분, 최대 8줄)
- 주제 예시: 시간복잡도, 메모리 관리, 동시성, 보안, 디자인 패턴, 알고리즘, 자료구조
"""

        prompt = f"""당신은 CS 교육 전문가입니다. 아래 커밋을 보고 **관련된 CS 지식**을 묻는 퀴즈를 생성하세요.

# 커밋 정보
{commits_text}

{quiz_instruction}

# JSON 형식
{example_output}

# 절대 규칙
1. 유효한 JSON만 출력 (마크다운 금지, questions 배열만)
2. 질문은 **CS 이론/원리** 중심 (코드 세부사항 금지)
3. {"**주제 선택 시**: codeContext는 개념 설명을 위한 일반적 예시 (커밋과 무관해도 됨)" if selected_topic else "**주제 미선택 시**: codeContext는 위 커밋의 실제 코드에서 가져올 것"}
4. **codeContext는 단일 코드 조각만** ("변경 전/후" 비교 금지)
5. 문자열 이스케이프: \\n, \\"
6. 변수 직접 참조 금지
7. 오답도 교육적으로 (흔한 오개념 포함)

{"**중요**: 주제에 대한 전반적인 CS 지식을 다루세요. 커밋 코드의 구체적인 내용은 무시하고, 해당 주제의 핵심 개념과 실무 적용을 학습할 수 있는 퀴즈를 만드세요." if selected_topic else "**중요**: codeContext는 위 '커밋 정보'의 실제 코드에서 가져와야 합니다. 변경 전/후를 비교하지 말고 해당 기술을 보여주는 코드 조각만 제시하세요."}
{"주제 '" + selected_topic + "'에 대한 교육적 퀴즈를 JSON으로 생성하세요:" if selected_topic else "커밋에서 사용된 기술을 보고, 관련 CS 지식을 묻는 퀴즈를 JSON으로 생성하세요:"}"""

        return prompt

    async def generate_learning_session(
        self,
        commits: List[CommitDetailResponse],
        question_count: int = 5,
        difficulty: str = "medium",
        selected_topic: Optional[str] = None
    ) -> QuizGenerationResponse:
        """
        퀴즈 생성

        Args:
            commits: 커밋 상세 정보 목록
            question_count: 생성할 퀴즈 개수
            difficulty: 난이도
            selected_topic: 선택된 주제 제목 (선택 시 해당 주제에 집중)

        Returns:
            QuizGenerationResponse: 생성된 퀴즈
        """
        try:
            topic_info = f", 주제: {selected_topic}" if selected_topic else ""
            logger.info(f"[LearningSession] 퀴즈 생성 시작: {len(commits)}개 커밋, 난이도: {difficulty}{topic_info}")

            # 프롬프트 구성
            prompt = self._build_unified_prompt(commits, question_count, difficulty, selected_topic)
            logger.info(f"[LearningSession] 프롬프트 길이: {len(prompt)} 문자")

            # Gemini API 호출
            logger.info(f"[LearningSession] Gemini API 호출 중...")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.4,
                max_tokens=8000
            )

            logger.info(f"[LearningSession] Gemini 응답 키: {list(response_data.keys())}")

            # 응답 검증
            if "questions" not in response_data:
                raise ValueError("응답에 'questions' 필드가 없습니다.")

            # 퀴즈 파싱
            questions = []
            for idx, q_data in enumerate(response_data["questions"]):
                try:
                    if "id" not in q_data:
                        q_data["id"] = f"q{idx + 1}"

                    # 타입 정규화
                    q_type = str(q_data.get("type", "multiple")).lower()
                    q_data["type"] = q_type

                    question = QuizQuestionResponse(**q_data)
                    questions.append(question)
                except Exception as e:
                    logger.warning(f"질문 {idx + 1} 파싱 실패: {str(e)}")
                    continue

            quiz_response = QuizGenerationResponse(
                questions=questions,
                metadata={
                    "totalCommits": len(commits),
                    "requestedCount": question_count,
                    "generatedCount": len(questions),
                    "difficulty": difficulty,
                    "generatedAt": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"[LearningSession] 퀴즈 생성 완료: {len(questions)}개")

            return quiz_response

        except Exception as e:
            logger.error(f"[LearningSession] 퀴즈 생성 실패: {str(e)}")
            raise ValueError(f"퀴즈 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_learning_session_service = None


def get_learning_session_service() -> LearningSessionService:
    """LearningSessionService 싱글톤 인스턴스 반환"""
    global _learning_session_service
    if _learning_session_service is None:
        _learning_session_service = LearningSessionService()
    return _learning_session_service

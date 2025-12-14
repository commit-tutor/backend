"""
퀴즈 생성 서비스
커밋 분석을 통해 CS 지식 퀴즈 생성
"""

from typing import List, Optional
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import QuizQuestionResponse, QuizGenerationResponse
from app.schemas.analysis import CommitDetailResponse
from app.core.config import settings

logger = logging.getLogger(__name__)


class QuizGenerator:
    """커밋 기반 CS 퀴즈를 생성하는 서비스"""

    def __init__(self):
        # 퀴즈 생성용 모델 사용
        self.gemini_service = get_gemini_service(model_name=settings.OPENROUTER_QUIZ_MODEL)
        self._max_patch_preview_length = 1200
        logger.info(f"QuizGenerator 초기화 (모델: {settings.OPENROUTER_QUIZ_MODEL})")

    def _build_quiz_prompt(
        self,
        commits: List[CommitDetailResponse],
        question_count: int,
        selected_topic: Optional[str] = None
    ) -> str:
        """퀴즈 생성 프롬프트 구성"""

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

        # 퀴즈 예시 (코드가 있는 경우와 없는 경우 모두 포함)
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
    },
    {
      "id": "q2",
      "type": "multiple",
      "question": "데이터베이스 트랜잭션의 ACID 속성 중 Consistency(일관성)가 보장하는 것은?",
      "codeContext": null,
      "options": [
        "트랜잭션 전후에 데이터베이스가 정의된 규칙과 제약조건을 만족함",
        "동시에 실행되는 트랜잭션들이 서로 영향을 주지 않음",
        "트랜잭션이 완전히 실행되거나 전혀 실행되지 않음",
        "커밋된 데이터는 영구적으로 저장됨"
      ],
      "correctAnswer": 0,
      "explanation": "일관성은 트랜잭션 실행 전후에 데이터베이스가 일관된 상태를 유지하고, 모든 제약조건(foreign key, unique 등)을 만족함을 보장합니다."
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
4. **codeContext는 개념 이해에 꼭 필요한 경우에만 포함** (개념 설명만으로 충분하면 생략)

## 좋은 예시 (주제 선택 시)
주제: "비동기 프로그래밍" →
질문: "JavaScript에서 Promise의 then() 체이닝이 콜백 헬(callback hell)을 해결하는 원리는?"
codeContext: "fetch('/api/user')\\n  .then(res => res.json())\\n  .then(data => console.log(data))"
설명: Promise 체이닝의 동작을 코드로 보여주는 것이 이해에 도움

주제: "REST API 설계" →
질문: "RESTful API에서 PUT과 PATCH의 차이점은?"
codeContext: null (또는 생략)
설명: 개념 설명만으로 충분한 경우 코드 불필요

주제: "캐싱 전략" →
질문: "웹 애플리케이션에서 LRU(Least Recently Used) 캐시의 주요 장점은?"
codeContext: null
설명: 이론적 질문은 코드 없이도 충분

## 나쁜 예시 (주제 선택 시 금지)
❌ "이 커밋의 변수명이 바뀐 이유는?" (커밋에 집중)
❌ "다음 코드의 버그는?" (코드 세부사항)
❌ 개념 설명만으로 충분한데도 불필요한 코드 포함
❌ 커밋 코드를 그대로 codeContext로 사용 (일반적 예시를 써야 함)

# 퀴즈 요구사항
- {question_count}개의 객관식 (4지선다)
- **주제: {selected_topic}의 전반적인 개념**을 다루세요
- **codeContext: 코드가 개념 이해에 필수적인 경우에만 포함** (불필요하면 null 또는 생략, 최대 8줄)
- 각 문제는 주제의 다른 측면을 다루세요 (중복 방지)
"""
        else:
            # 주제가 선택되지 않은 경우: 커밋 코드 기반 퀴즈
            quiz_instruction = f"""
# 퀴즈 작성 원칙
위 커밋의 **실제 코드**에서 사용된 기술/패턴을 보고, 그와 관련된 **CS 이론과 원리**를 물으세요.

## 좋은 예시
커밋에서 `async/await` 사용 발견 →
질문: "비동기 함수에서 await 키워드의 주요 역할은?"
codeContext: "async function fetchData() {{\\n  const result = await db.query('SELECT * FROM users');\\n  return result;\\n}}"
설명: 코드가 개념 이해에 도움

커밋에서 데이터베이스 트랜잭션 사용 발견 →
질문: "데이터베이스 트랜잭션의 ACID 속성 중 Atomicity(원자성)가 보장하는 것은?"
codeContext: null
설명: 이론적 질문은 코드 없이도 충분

커밋에서 캐싱 로직 발견 →
질문: "웹 애플리케이션에서 캐싱을 사용하는 주요 목적은?"
codeContext: null
설명: 개념 설명만으로 충분한 경우

## 나쁜 예시 (금지)
❌ "이 변수명은 뭔가요?" (지엽적)
❌ codeContext를 임의로 만든 예시 (실제 커밋 코드를 사용해야 함)
❌ "변경 전/변경 후" 형식 (그냥 코드만 제시)
❌ 개념 설명만으로 충분한데도 불필요한 코드 포함

# 퀴즈 요구사항
- {question_count}개의 객관식 (4지선다)
- **실제 커밋 코드**에서 발견한 기술/개념과 **관련된 CS 원리**를 물으세요
- **codeContext: 코드가 개념 이해에 필수적인 경우에만 포함** (불필요하면 null 또는 생략, 최대 8줄)
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
3. **codeContext는 개념 이해에 필수적인 경우에만 포함** (불필요하면 null 또는 생략)
4. {"**주제 선택 시**: codeContext는 개념 설명을 위한 일반적 예시 (커밋과 무관해도 됨, 필요시에만)" if selected_topic else "**주제 미선택 시**: codeContext는 위 커밋의 실제 코드에서 가져올 것 (필요시에만)"}
5. **codeContext는 단일 코드 조각만** ("변경 전/후" 비교 금지)
6. 문자열 이스케이프: \\n, \\"
7. 변수 직접 참조 금지
8. 오답도 교육적으로 (흔한 오개념 포함)

{"**중요**: 주제에 대한 전반적인 CS 지식을 다루세요. 커밋 코드의 구체적인 내용은 무시하고, 해당 주제의 핵심 개념과 실무 적용을 학습할 수 있는 퀴즈를 만드세요. 코드는 필요한 경우에만 포함하세요." if selected_topic else "**중요**: codeContext는 개념 이해에 도움이 되는 경우에만 포함하세요. 이론적 질문은 코드 없이도 충분합니다. 코드를 포함하는 경우 위 '커밋 정보'의 실제 코드에서 가져와야 하며, 변경 전/후를 비교하지 말고 해당 기술을 보여주는 코드 조각만 제시하세요."}
{"주제 '" + selected_topic + "'에 대한 교육적 퀴즈를 JSON으로 생성하세요:" if selected_topic else "커밋에서 사용된 기술을 보고, 관련 CS 지식을 묻는 퀴즈를 JSON으로 생성하세요:"}"""

        return prompt

    async def generate_quiz(
        self,
        commits: List[CommitDetailResponse],
        question_count: int = 5,
        selected_topic: Optional[str] = None
    ) -> QuizGenerationResponse:
        """
        커밋 기반 CS 퀴즈 생성

        Args:
            commits: 커밋 상세 정보 목록
            question_count: 생성할 퀴즈 개수
            selected_topic: 선택된 주제 제목 (선택 시 해당 주제에 집중)

        Returns:
            QuizGenerationResponse: 생성된 퀴즈
        """
        try:
            topic_info = f", 주제: {selected_topic}" if selected_topic else ""
            logger.info(f"[QuizGenerator] 퀴즈 생성 시작: {len(commits)}개 커밋{topic_info}")

            # 프롬프트 구성
            prompt = self._build_quiz_prompt(commits, question_count, selected_topic)
            logger.info(f"[QuizGenerator] 프롬프트 길이: {len(prompt)} 문자")

            # Gemini API 호출
            logger.info(f"[QuizGenerator] Gemini API 호출 중...")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.4,
                max_tokens=8000
            )

            logger.info(f"[QuizGenerator] Gemini 응답 키: {list(response_data.keys())}")

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
                    "generatedAt": datetime.utcnow().isoformat()
                }
            )

            logger.info(f"[QuizGenerator] 퀴즈 생성 완료: {len(questions)}개")

            return quiz_response

        except Exception as e:
            logger.error(f"[QuizGenerator] 퀴즈 생성 실패: {str(e)}")
            raise ValueError(f"퀴즈 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_quiz_generator = None


def get_quiz_generator() -> QuizGenerator:
    """QuizGenerator 싱글톤 인스턴스 반환"""
    global _quiz_generator
    if _quiz_generator is None:
        _quiz_generator = QuizGenerator()
    return _quiz_generator

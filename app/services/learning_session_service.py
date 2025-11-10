"""
학습 세션 통합 서비스
퀴즈와 코드 리뷰를 단일 API 호출로 생성하여 토큰 절약
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import QuizQuestionResponse, QuizGenerationResponse
from app.schemas.analysis import CommitDetailResponse, AIAnalysisResponse, CodeQuality

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
        difficulty: str
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

        # 통합 예시
        example_output = """{
  "quiz": {
    "questions": [
      {
        "id": "q1",
        "type": "multiple",
        "question": "이 코드는 JWT 기반 stateless 인증을 사용합니다. stateless 인증의 주요 장점은?",
        "codeContext": "// 변경 전\\nfunction login(user) {\\n  session.set(user.id, user);\\n  return { sessionId: generateId() };\\n}\\n\\n// 변경 후\\nfunction login(user) {\\n  return { token: jwt.sign({ id: user.id }, SECRET) };\\n}",
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
  },
  "review": {
    "summary": "이 커밋은 세션 기반 인증을 JWT로 전환하여 stateless 아키텍처를 구현했습니다.",
    "quality": {
      "readability": 85,
      "performance": 80,
      "security": 90
    },
    "suggestions": [
      "JWT secret을 환경 변수로 관리하세요",
      "토큰 만료 시간(exp)을 설정하여 보안을 강화하세요"
    ],
    "potentialBugs": [
      "토큰 갱신(refresh token) 메커니즘이 없어 장기 세션 관리가 어려울 수 있습니다"
    ]
  }
}"""

        prompt = f"""당신은 컴퓨터 과학 교육 전문가입니다. 아래 커밋을 분석하여 **퀴즈와 코드 리뷰를 동시에** 생성하세요.

# 커밋 정보
{commits_text}

# 요구사항
## 퀴즈 (quiz)
- 총 {question_count}개의 객관식 퀴즈 (4지선다)
- 난이도: {difficulty} - {difficulty_guide.get(difficulty, '')}
- CS 원리를 묻는 질문 (시간복잡도, 동시성, 보안, 아키텍처 등)
- 주제: 자료구조, 알고리즘, 동시성/병렬성, 메모리, 네트워크, 보안, 설계 패턴, DB, 아키텍처

## 코드 리뷰 (review)
- summary: 커밋의 핵심 변경사항 요약 (2-3문장)
- quality: 코드 품질 점수 (readability, performance, security: 0-100)
- suggestions: 구체적인 개선 제안 (3-5개)
- potentialBugs: 잠재적 버그나 문제점 (있다면)

# JSON 출력 형식 (필수)
{example_output}

# 중요 규칙
1. **유효한 JSON만 출력** (마크다운, 주석 금지)
2. **quiz와 review를 모두 포함**한 단일 JSON 객체
3. codeContext는 변경 전/후 코드 포함 (최대 15줄)
4. 문자열 이스케이프: \\n으로 줄바꿈, \\" 처리
5. 변수 직접 참조 금지
6. 설명과 제안은 구체적이고 실용적으로

이제 통합 학습 자료를 JSON으로 생성하세요:"""

        return prompt

    async def generate_learning_session(
        self,
        commits: List[CommitDetailResponse],
        question_count: int = 5,
        difficulty: str = "medium"
    ) -> Dict[str, Any]:
        """
        퀴즈와 코드 리뷰를 한 번에 생성

        Args:
            commits: 커밋 상세 정보 목록
            question_count: 생성할 퀴즈 개수
            difficulty: 난이도

        Returns:
            {"quiz": QuizGenerationResponse, "review": AIAnalysisResponse}
        """
        try:
            logger.info(f"[LearningSession] 통합 생성 시작: {len(commits)}개 커밋, 난이도: {difficulty}")

            # 통합 프롬프트 구성
            prompt = self._build_unified_prompt(commits, question_count, difficulty)
            logger.info(f"[LearningSession] 프롬프트 길이: {len(prompt)} 문자")

            # Gemini API 단일 호출
            logger.info(f"[LearningSession] Gemini API 호출 중... (통합 요청)")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.4,
                max_tokens=10000  # 퀴즈 + 리뷰 모두 담을 충분한 토큰
            )

            logger.info(f"[LearningSession] Gemini 응답 키: {list(response_data.keys())}")

            # 응답 검증
            if "quiz" not in response_data or "review" not in response_data:
                raise ValueError("응답에 'quiz' 또는 'review' 필드가 없습니다.")

            # 퀴즈 파싱
            quiz_data = response_data["quiz"]
            if "questions" not in quiz_data:
                raise ValueError("quiz에 'questions' 필드가 없습니다.")

            questions = []
            for idx, q_data in enumerate(quiz_data["questions"]):
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

            # 리뷰 파싱
            review_data = response_data["review"]
            quality_data = review_data.get("quality", {})

            review_response = AIAnalysisResponse(
                summary=review_data.get("summary", ""),
                quality=CodeQuality(
                    readability=quality_data.get("readability", 0),
                    performance=quality_data.get("performance", 0),
                    security=quality_data.get("security", 0)
                ),
                suggestions=review_data.get("suggestions", []),
                potentialBugs=review_data.get("potentialBugs", [])
            )

            logger.info(f"[LearningSession] 생성 완료: 퀴즈 {len(questions)}개, 리뷰 제안 {len(review_response.suggestions)}개")

            return {
                "quiz": quiz_response,
                "review": review_response
            }

        except Exception as e:
            logger.error(f"[LearningSession] 생성 실패: {str(e)}")
            raise ValueError(f"학습 세션 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_learning_session_service = None


def get_learning_session_service() -> LearningSessionService:
    """LearningSessionService 싱글톤 인스턴스 반환"""
    global _learning_session_service
    if _learning_session_service is None:
        _learning_session_service = LearningSessionService()
    return _learning_session_service

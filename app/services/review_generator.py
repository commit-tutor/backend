"""
복습 자료 생성 서비스
퀴즈 결과를 분석하여 AI 기반 학습 문서 생성
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.review import ReviewSection

logger = logging.getLogger(__name__)


class ReviewGenerator:
    """복습 자료 생성기"""
    
    def __init__(self):
        self.gemini_service = get_gemini_service()
    
    def _build_review_prompt(
        self,
        quiz_title: str,
        quiz_topic: Optional[str],
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, Any],
        score: float
    ) -> str:
        """복습 자료 생성 프롬프트 구성"""
        
        # 정답/오답 분석
        correct_questions = []
        wrong_questions = []
        
        for question in questions:
            q_id = question.get("id")
            correct_answer = question.get("correctAnswer")
            user_answer = user_answers.get(q_id)
            
            is_correct = (user_answer == correct_answer or str(user_answer) == str(correct_answer))
            
            q_summary = {
                "id": q_id,
                "question": question.get("question"),
                "type": question.get("type"),
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "explanation": question.get("explanation"),
                "code_context": question.get("codeContext")
            }
            
            if is_correct:
                correct_questions.append(q_summary)
            else:
                wrong_questions.append(q_summary)
        
        # 프롬프트 구성
        topic_text = f"주제: {quiz_topic}" if quiz_topic else "일반 CS 주제"
        
        prompt = f"""당신은 교육 전문가입니다. 아래 퀴즈 결과를 분석하여 학습자가 복습할 수 있는 학습 문서를 생성하세요.

# 퀴즈 정보
- 제목: {quiz_title}
- {topic_text}
- 점수: {score:.1f}점
- 정답: {len(correct_questions)}개
- 오답: {len(wrong_questions)}개

# 정답 문제
{self._format_questions(correct_questions)}

# 오답 문제
{self._format_questions(wrong_questions)}

# 생성 요구사항
1. **전체 요약**: 퀴즈를 통해 다룬 핵심 개념을 3-4줄로 요약
2. **학습 섹션** (3-4개):
   - 각 섹션은 퀴즈에서 다룬 주요 개념을 심화 설명
   - 틀린 문제의 개념을 우선적으로 다룸
   - 각 섹션에는 핵심 포인트와 예제 포함
3. **관련 개념**: 추가로 알아두면 좋을 관련 개념 3-5개
4. **추가 학습 자료**: 더 공부하면 좋을 주제나 방향성 제시

# 출력 형식 (JSON)
{{
  "title": "복습 자료 제목 (간결하게)",
  "summary": "전체 요약 (3-4줄)",
  "sections": [
    {{
      "title": "섹션 제목",
      "content": "학습 내용 (마크다운 형식, 500-800자)",
      "key_points": ["핵심 포인트1", "핵심 포인트2", "핵심 포인트3"],
      "examples": ["예제 설명 또는 코드 예시"]
    }}
  ],
  "related_concepts": ["관련 개념1", "관련 개념2", "관련 개념3"],
  "further_reading": ["추가 학습 방향1", "추가 학습 방향2"]
}}

**중요**: 
- 마크다운 형식을 사용하여 가독성 높게 작성
- 코드 예제는 간결하고 핵심만 포함
- 학습자가 틀린 부분을 중점적으로 설명
- 실용적이고 실무에 도움되는 내용 작성
- 유효한 JSON만 반환 (코드 블록 없이)
"""
        
        return prompt
    
    def _format_questions(self, questions: List[Dict[str, Any]]) -> str:
        """문제 정보를 텍스트로 포맷팅"""
        if not questions:
            return "없음"
        
        result = []
        for q in questions:
            text = f"\n문제 {q['id']}: {q['question']}"
            if q.get('code_context'):
                text += f"\n코드: {q['code_context'][:200]}..."
            text += f"\n정답: {q['correct_answer']}"
            text += f"\n사용자 답: {q['user_answer']}"
            if q.get('explanation'):
                text += f"\n해설: {q['explanation']}"
            result.append(text)
        
        return "\n---\n".join(result)
    
    async def generate_review(
        self,
        quiz_title: str,
        quiz_topic: Optional[str],
        questions: List[Dict[str, Any]],
        user_answers: Dict[str, Any],
        score: float
    ) -> Dict[str, Any]:
        """
        복습 자료 생성
        
        Args:
            quiz_title: 퀴즈 제목
            quiz_topic: 퀴즈 주제
            questions: 퀴즈 문제 목록
            user_answers: 사용자 답안 (question_id: answer)
            score: 점수
        
        Returns:
            생성된 복습 자료 (JSON)
        """
        try:
            logger.info(f"[ReviewGenerator] 복습 자료 생성 시작: {quiz_title}, 점수: {score}점")
            
            # 프롬프트 구성
            prompt = self._build_review_prompt(
                quiz_title, quiz_topic, questions, user_answers, score
            )
            logger.info(f"[ReviewGenerator] 프롬프트 길이: {len(prompt)} 문자")
            
            # Gemini API 호출
            logger.info(f"[ReviewGenerator] Gemini API 호출 중...")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.5,  # 창의적이면서도 일관성 있게
                max_tokens=6000
            )
            
            logger.info(f"[ReviewGenerator] Gemini 응답 키: {list(response_data.keys())}")
            
            # 응답 검증
            required_keys = ["title", "summary", "sections"]
            for key in required_keys:
                if key not in response_data:
                    raise ValueError(f"응답에 '{key}' 필드가 없습니다.")
            
            if not isinstance(response_data["sections"], list):
                raise ValueError("'sections'는 배열이어야 합니다.")
            
            logger.info(f"[ReviewGenerator] 복습 자료 생성 완료: {len(response_data['sections'])}개 섹션")
            
            return response_data
            
        except Exception as e:
            logger.error(f"[ReviewGenerator] 복습 자료 생성 실패: {str(e)}")
            raise ValueError(f"복습 자료 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_review_generator = None


def get_review_generator() -> ReviewGenerator:
    """ReviewGenerator 싱글톤 인스턴스 반환"""
    global _review_generator
    if _review_generator is None:
        _review_generator = ReviewGenerator()
    return _review_generator

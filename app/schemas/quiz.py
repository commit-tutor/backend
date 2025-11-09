"""
퀴즈 관련 스키마 정의
프론트엔드 QuizQuestion 인터페이스와 일치하는 구조
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal


class QuizQuestionBase(BaseModel):
    """퀴즈 질문 기본 스키마"""
    id: str = Field(..., description="질문 고유 ID")
    type: Literal["multiple", "short"] = Field(..., description="질문 타입: 객관식(multiple) 또는 주관식(short)")
    question: str = Field(..., description="질문 내용")
    codeContext: Optional[str] = Field(None, description="질문과 관련된 코드 컨텍스트")
    options: Optional[List[str]] = Field(None, description="객관식 선택지 (type이 'multiple'인 경우 필수)")
    correctAnswer: Union[int, str] = Field(..., description="정답 (객관식: 인덱스, 주관식: 문자열)")
    explanation: Optional[str] = Field(None, description="정답 해설")


class QuizQuestionCreate(QuizQuestionBase):
    """퀴즈 질문 생성 스키마"""
    pass


class QuizQuestionResponse(QuizQuestionBase):
    """퀴즈 질문 응답 스키마"""

    class Config:
        json_schema_extra = {
            "example": {
                "id": "q1",
                "type": "multiple",
                "question": "이 코드 변경의 주요 목적은 무엇인가요?",
                "codeContext": "- const token = createToken(payload)\n+ const token = jwt.sign(payload, secret)",
                "options": [
                    "보안 강화를 위해 JWT 라이브러리 사용",
                    "코드 가독성 향상",
                    "성능 최적화",
                    "버그 수정"
                ],
                "correctAnswer": 0,
                "explanation": "jwt.sign()을 사용하여 표준 JWT 토큰 생성 방식으로 변경했습니다. 이는 보안성과 호환성을 높이는 베스트 프랙티스입니다."
            }
        }


class QuizGenerationRequest(BaseModel):
    """퀴즈 생성 요청 스키마"""
    commitShas: List[str] = Field(..., description="퀴즈를 생성할 커밋 SHA 목록", min_length=1)
    difficulty: Optional[Literal["easy", "medium", "hard"]] = Field(
        "medium",
        description="퀴즈 난이도"
    )
    questionCount: Optional[int] = Field(
        5,
        description="생성할 퀴즈 개수 (기본: 5개)",
        ge=3,
        le=10
    )

    class Config:
        json_schema_extra = {
            "example": {
                "commitShas": ["abc123def456", "789ghi012jkl"],
                "difficulty": "medium",
                "questionCount": 5
            }
        }


class QuizGenerationResponse(BaseModel):
    """퀴즈 생성 응답 스키마"""
    questions: List[QuizQuestionResponse] = Field(..., description="생성된 퀴즈 목록")
    metadata: Optional[dict] = Field(None, description="추가 메타데이터")

    class Config:
        json_schema_extra = {
            "example": {
                "questions": [
                    {
                        "id": "q1",
                        "type": "multiple",
                        "question": "이 함수의 시간 복잡도는?",
                        "codeContext": "def find_max(arr):\n    return max(arr)",
                        "options": ["O(1)", "O(n)", "O(log n)", "O(n²)"],
                        "correctAnswer": 1,
                        "explanation": "max() 함수는 배열을 순회하므로 O(n)입니다."
                    }
                ],
                "metadata": {
                    "totalCommits": 2,
                    "generatedAt": "2025-01-09T12:00:00Z"
                }
            }
        }

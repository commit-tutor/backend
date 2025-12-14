"""
나의 퀴즈 관련 스키마
퀴즈 저장, 조회, 제출 등의 요청/응답 모델
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QuizSaveRequest(BaseModel):
    """퀴즈 저장 요청"""
    title: str = Field(..., description="퀴즈 제목")
    description: Optional[str] = Field(None, description="퀴즈 설명")
    commit_shas: List[str] = Field(..., description="커밋 SHA 목록")
    repository_info: Optional[Dict[str, Any]] = Field(None, description="저장소 정보")
    question_count: int = Field(..., description="문제 개수")
    selected_topic: Optional[str] = Field(None, description="선택된 주제")
    questions: List[Dict[str, Any]] = Field(..., description="퀴즈 문제들")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "React Hooks 학습",
                "description": "useState와 useEffect 관련 퀴즈",
                "commit_shas": ["owner/repo:abc123"],
                "repository_info": {"owner": "facebook", "repo": "react"},
                "question_count": 5,
                "selected_topic": "React Hooks",
                "questions": []
            }
        }


class QuizSubmitRequest(BaseModel):
    """퀴즈 제출 요청"""
    user_answers: Dict[str, Any] = Field(..., description="사용자 답안 (question_id: answer)")
    duration_seconds: Optional[int] = Field(None, description="소요 시간(초) - 사용하지 않음")

    class Config:
        json_schema_extra = {
            "example": {
                "user_answers": {"q1": 0, "q2": "async/await", "q3": 2},
                "duration_seconds": 180
            }
        }


class QuizResponse(BaseModel):
    """퀴즈 응답"""
    id: int
    title: str
    description: Optional[str]
    commit_shas: List[str]
    repository_info: Optional[Dict[str, Any]]
    question_count: int
    selected_topic: Optional[str]
    questions: List[Dict[str, Any]]
    is_completed: bool
    completed_at: Optional[datetime]
    score: Optional[float]
    correct_answers: Optional[int]
    wrong_answers: Optional[int]
    duration_seconds: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class QuizListResponse(BaseModel):
    """퀴즈 목록 응답"""
    quizzes: List[QuizResponse]
    total: int
    completed: int
    pending: int


class QuizSubmitResponse(BaseModel):
    """퀴즈 제출 결과"""
    quiz_id: int
    score: float
    correct_answers: int
    wrong_answers: int
    is_passed: bool
    feedback: Optional[str]

"""
복습 자료 관련 스키마
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ReviewSection(BaseModel):
    """복습 자료 섹션"""
    title: str = Field(..., description="섹션 제목")
    content: str = Field(..., description="학습 내용 (마크다운)")
    key_points: List[str] = Field(..., description="핵심 포인트")
    examples: Optional[List[str]] = Field(None, description="예제 코드 또는 설명")


class ReviewGenerateRequest(BaseModel):
    """복습 자료 생성 요청"""
    quiz_id: int = Field(..., description="퀴즈 ID")


class ReviewResponse(BaseModel):
    """복습 자료 응답"""
    id: int
    user_id: int
    quiz_id: int
    title: str
    summary: str
    sections: List[Dict[str, Any]]  # ReviewSection 리스트
    related_concepts: Optional[List[str]]
    further_reading: Optional[List[str]]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # 퀴즈 정보 포함
    quiz_title: Optional[str] = None
    quiz_score: Optional[float] = None

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    """복습 자료 목록 응답"""
    reviews: List[ReviewResponse]
    total: int

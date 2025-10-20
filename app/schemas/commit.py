from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CommitBase(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    diff: Optional[str] = None


class CommitCreate(CommitBase):
    """커밋 생성 스키마"""
    pass


class CommitResponse(CommitBase):
    """커밋 응답 스키마"""
    id: str
    created_at: datetime
    score: Optional[int] = None

    class Config:
        from_attributes = True


class CommitAnalysis(BaseModel):
    """커밋 분석 결과 스키마"""
    message: str
    score: int = Field(..., ge=0, le=100, description="커밋 메시지 점수 (0-100)")
    suggestions: List[str] = Field(default_factory=list, description="개선 제안")
    category: str = Field(..., description="커밋 카테고리 (feature, fix, docs, etc.)")
    improved_message: Optional[str] = Field(None, description="개선된 커밋 메시지")

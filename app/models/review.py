"""
Review 모델 - 퀴즈 복습 자료
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Review(Base):
    """
    복습 자료 모델
    퀴즈 완료 후 생성되는 AI 기반 학습 문서
    """
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 복습 자료 내용
    title = Column(String, nullable=False)  # 복습 자료 제목
    summary = Column(Text, nullable=False)  # 전체 요약
    
    # 섹션별 내용 (JSON)
    sections = Column(JSON, nullable=False)  # List[Section] - 각 섹션별 학습 내용
    # Section 구조: {
    #   "title": "섹션 제목",
    #   "content": "학습 내용 (마크다운)",
    #   "key_points": ["핵심 포인트1", "핵심 포인트2"],
    #   "examples": ["예제 코드 또는 설명"]
    # }
    
    # 추가 학습 자료
    related_concepts = Column(JSON, nullable=True)  # List[str] - 관련 개념들
    further_reading = Column(JSON, nullable=True)  # List[str] - 추가 학습 권장 사항
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계
    user = relationship("User", back_populates="reviews")
    quiz = relationship("Quiz", back_populates="reviews")

    def __repr__(self):
        return f"<Review(id={self.id}, title={self.title}, quiz_id={self.quiz_id})>"

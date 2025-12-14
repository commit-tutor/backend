"""
Quiz 모델 - 퀴즈 및 퀴즈 시도 기록
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Quiz(Base):
    """
    퀴즈 모델
    사용자가 생성한 퀴즈 정보 저장
    """
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 퀴즈 메타데이터
    title = Column(String, nullable=False)  # 퀴즈 제목 (예: "React Hooks 학습")
    description = Column(Text, nullable=True)  # 퀴즈 설명
    
    # 커밋 정보
    commit_shas = Column(JSON, nullable=False)  # List[str] - 퀴즈 생성에 사용된 커밋 SHA 목록
    repository_info = Column(JSON, nullable=True)  # 저장소 정보 (owner, repo, full_name 등)
    
    # 퀴즈 설정
    question_count = Column(Integer, nullable=False)  # 문제 개수
    selected_topic = Column(String, nullable=True)  # 선택된 주제 (없으면 전체)
    
    # 퀴즈 데이터 (JSON)
    questions = Column(JSON, nullable=False)  # List[QuizQuestion] - 실제 퀴즈 문제들
    
    # 완료 여부
    is_completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 점수 (완료 시 저장)
    score = Column(Float, nullable=True)  # 정답률 (0-100)
    correct_answers = Column(Integer, nullable=True)  # 맞춘 문제 수
    wrong_answers = Column(Integer, nullable=True)  # 틀린 문제 수
    
    # 소요 시간 (초)
    duration_seconds = Column(Integer, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계
    user = relationship("User", back_populates="quizzes")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="quiz", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Quiz(id={self.id}, title={self.title}, completed={self.is_completed})>"


class QuizAttempt(Base):
    """
    퀴즈 시도 기록
    사용자가 퀴즈를 풀 때마다 저장 (재시도 지원)
    """
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 시도 결과
    score = Column(Float, nullable=False)  # 정답률 (0-100)
    correct_answers = Column(Integer, nullable=False)
    wrong_answers = Column(Integer, nullable=False)
    
    # 사용자 답안 (JSON)
    user_answers = Column(JSON, nullable=False)  # Dict[question_id, user_answer]
    
    # 소요 시간 (초)
    duration_seconds = Column(Integer, nullable=True)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # 관계
    quiz = relationship("Quiz", back_populates="attempts")

    def __repr__(self):
        return f"<QuizAttempt(id={self.id}, quiz_id={self.quiz_id}, score={self.score})>"

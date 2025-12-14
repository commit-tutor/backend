"""
복습 자료 관련 API 엔드포인트
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.quiz import Quiz, QuizAttempt
from app.models.review import Review
from app.schemas.review import ReviewGenerateRequest, ReviewResponse, ReviewListResponse
from app.api.dependencies import get_current_user
from app.services.review_generator import get_review_generator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate", response_model=ReviewResponse)
def generate_review(
    request: ReviewGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    퀴즈 결과 기반 복습 자료 생성
    
    퀴즈 완료 후 호출하여 AI 기반 학습 문서를 생성합니다.
    """
    try:
        logger.info(f"[복습 자료 생성] 사용자 {current_user.username}이(가) 퀴즈 ID {request.quiz_id} 복습 자료 생성 요청")
        
        # 퀴즈 조회 (attempts를 eager loading)
        result = db.execute(
            select(Quiz)
            .options(selectinload(Quiz.attempts))
            .where(
                Quiz.id == request.quiz_id,
                Quiz.user_id == current_user.id
            )
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="퀴즈를 찾을 수 없습니다."
            )
        
        if not quiz.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="완료된 퀴즈만 복습 자료를 생성할 수 있습니다."
            )
        
        # 이미 생성된 복습 자료가 있는지 확인
        existing_review = db.execute(
            select(Review).where(
                Review.quiz_id == request.quiz_id,
                Review.user_id == current_user.id
            )
        )
        existing = existing_review.scalar_one_or_none()
        
        if existing:
            logger.info(f"[복습 자료 생성] 기존 복습 자료 반환 (ID: {existing.id})")
            return ReviewResponse(
                **{
                    **existing.__dict__,
                    "quiz_title": quiz.title,
                    "quiz_score": quiz.score
                }
            )
        
        # 최근 시도 기록에서 사용자 답안 가져오기
        # 별도 쿼리로 최신 attempt 조회
        latest_attempt_result = db.execute(
            select(QuizAttempt)
            .where(QuizAttempt.quiz_id == request.quiz_id)
            .order_by(desc(QuizAttempt.created_at))
            .limit(1)
        )
        latest_attempt = latest_attempt_result.scalar_one_or_none()
        
        if not latest_attempt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="퀴즈 시도 기록이 없습니다."
            )
        
        user_answers = latest_attempt.user_answers.get("answers", {})
        
        # AI 복습 자료 생성 (동기 호출)
        review_generator = get_review_generator()
        # review_generator.generate_review가 async인 경우 동기로 변경해야 함
        # 여기서는 임시로 import asyncio를 사용하거나, generate_review를 동기 함수로 변경
        import asyncio
        review_data = asyncio.run(review_generator.generate_review(
            quiz_title=quiz.title,
            quiz_topic=quiz.selected_topic,
            questions=quiz.questions,
            user_answers=user_answers,
            score=quiz.score or 0
        ))
        
        logger.info(f"[복습 자료 생성] AI 생성 완료: {review_data.get('title')}")
        
        # DB에 저장
        review = Review(
            user_id=current_user.id,
            quiz_id=quiz.id,
            title=review_data["title"],
            summary=review_data["summary"],
            sections=review_data["sections"],
            related_concepts=review_data.get("related_concepts"),
            further_reading=review_data.get("further_reading")
        )
        
        db.add(review)
        db.commit()
        db.refresh(review)
        
        logger.info(f"[복습 자료 생성] DB 저장 완료 (ID: {review.id})")
        
        return ReviewResponse(
            **{
                **review.__dict__,
                "quiz_title": quiz.title,
                "quiz_score": quiz.score
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[복습 자료 생성] 오류: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"복습 자료 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("", response_model=ReviewListResponse)
def get_my_reviews(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    나의 복습 자료 목록 조회
    
    생성된 모든 복습 자료를 최신순으로 반환합니다.
    """
    try:
        logger.info(f"[복습 자료 목록] 사용자 {current_user.username}의 복습 자료 조회")
        
        # 복습 자료 조회 (최신순)
        result = db.execute(
            select(Review)
            .where(Review.user_id == current_user.id)
            .order_by(desc(Review.created_at))
            .offset(skip)
            .limit(limit)
        )
        reviews = result.scalars().all()
        
        # 퀴즈 정보 포함하여 반환
        reviews_with_quiz = []
        for review in reviews:
            quiz_result = db.execute(
                select(Quiz).where(Quiz.id == review.quiz_id)
            )
            quiz = quiz_result.scalar_one_or_none()
            
            reviews_with_quiz.append(
                ReviewResponse(
                    **{
                        **review.__dict__,
                        "quiz_title": quiz.title if quiz else None,
                        "quiz_score": quiz.score if quiz else None
                    }
                )
            )
        
        # 전체 개수 조회
        count_result = db.execute(
            select(Review).where(Review.user_id == current_user.id)
        )
        total = len(count_result.scalars().all())
        
        logger.info(f"[복습 자료 목록] {total}개 중 {len(reviews)}개 반환")
        
        return ReviewListResponse(
            reviews=reviews_with_quiz,
            total=total
        )
        
    except Exception as e:
        logger.error(f"[복습 자료 목록] 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"복습 자료 목록 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review_detail(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    복습 자료 상세 조회
    """
    try:
        logger.info(f"[복습 자료 상세] 사용자 {current_user.username}이(가) 복습 자료 ID {review_id} 조회")
        
        result = db.execute(
            select(Review).where(
                Review.id == review_id,
                Review.user_id == current_user.id
            )
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="복습 자료를 찾을 수 없습니다."
            )
        
        # 퀴즈 정보 포함
        quiz_result = db.execute(
            select(Quiz).where(Quiz.id == review.quiz_id)
        )
        quiz = quiz_result.scalar_one_or_none()
        
        return ReviewResponse(
            **{
                **review.__dict__,
                "quiz_title": quiz.title if quiz else None,
                "quiz_score": quiz.score if quiz else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[복습 자료 상세] 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"복습 자료 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    복습 자료 삭제
    """
    try:
        logger.info(f"[복습 자료 삭제] 사용자 {current_user.username}이(가) 복습 자료 ID {review_id} 삭제 요청")
        
        result = db.execute(
            select(Review).where(
                Review.id == review_id,
                Review.user_id == current_user.id
            )
        )
        review = result.scalar_one_or_none()
        
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="복습 자료를 찾을 수 없습니다."
            )
        
        db.delete(review)
        db.commit()
        
        logger.info(f"[복습 자료 삭제] 복습 자료 ID {review_id} 삭제 완료")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[복습 자료 삭제] 오류: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"복습 자료 삭제 중 오류가 발생했습니다: {str(e)}"
        )

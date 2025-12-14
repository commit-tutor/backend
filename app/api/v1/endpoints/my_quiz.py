"""
나의 퀴즈 API 엔드포인트
퀴즈 저장, 조회, 제출 기능
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc
from typing import Optional
import logging
from datetime import datetime

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.my_quiz import (
    QuizSaveRequest,
    QuizSubmitRequest,
    QuizResponse,
    QuizListResponse,
    QuizSubmitResponse
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def save_quiz(
    request: QuizSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    퀴즈 저장 (생성)
    
    퀴즈를 생성하면 자동으로 DB에 저장됩니다.
    """
    try:
        logger.info(f"[퀴즈 저장] 사용자 {current_user.username}이(가) 퀴즈 저장 요청")
        
        # Quiz 객체 생성
        quiz = Quiz(
            user_id=current_user.id,
            title=request.title,
            description=request.description,
            commit_shas=request.commit_shas,
            repository_info=request.repository_info,
            question_count=request.question_count,
            selected_topic=request.selected_topic,
            questions=request.questions,
            is_completed=False
        )
        
        db.add(quiz)
        db.commit()
        db.refresh(quiz)
        
        logger.info(f"[퀴즈 저장] 퀴즈 ID {quiz.id} 저장 완료")
        
        return quiz
        
    except Exception as e:
        logger.error(f"[퀴즈 저장] 오류: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 저장 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("", response_model=QuizListResponse)
def get_my_quizzes(
    is_completed: Optional[bool] = Query(None, description="완료 여부 필터 (true: 완료, false: 미완료, null: 전체)"),
    limit: int = Query(50, ge=1, le=100, description="최대 조회 개수"),
    offset: int = Query(0, ge=0, description="시작 위치"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    나의 퀴즈 목록 조회
    
    완료/미완료 필터링 가능
    """
    try:
        logger.info(f"[퀴즈 조회] 사용자 {current_user.username} 퀴즈 목록 요청 (완료: {is_completed})")
        
        # 기본 쿼리
        query = select(Quiz).where(Quiz.user_id == current_user.id)
        
        # 완료 여부 필터
        if is_completed is not None:
            query = query.where(Quiz.is_completed == is_completed)
        
        # 최신순 정렬
        query = query.order_by(desc(Quiz.created_at))
        
        # 페이지네이션
        query = query.limit(limit).offset(offset)
        
        # 퀴즈 목록 조회
        result = db.execute(query)
        quizzes = result.scalars().all()
        
        # 통계 조회
        total_query = select(func.count(Quiz.id)).where(Quiz.user_id == current_user.id)
        total_result = db.execute(total_query)
        total = total_result.scalar()
        
        completed_query = select(func.count(Quiz.id)).where(
            Quiz.user_id == current_user.id,
            Quiz.is_completed == True
        )
        completed_result = db.execute(completed_query)
        completed = completed_result.scalar()
        
        pending = total - completed
        
        logger.info(f"[퀴즈 조회] {len(quizzes)}개 퀴즈 조회 완료 (전체: {total}, 완료: {completed}, 미완료: {pending})")
        
        return QuizListResponse(
            quizzes=quizzes,
            total=total,
            completed=completed,
            pending=pending
        )
        
    except Exception as e:
        logger.error(f"[퀴즈 조회] 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{quiz_id}", response_model=QuizResponse)
def get_quiz_by_id(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 퀴즈 상세 조회
    """
    try:
        logger.info(f"[퀴즈 상세 조회] 사용자 {current_user.username}이(가) 퀴즈 ID {quiz_id} 조회")
        
        result = db.execute(
            select(Quiz).where(
                Quiz.id == quiz_id,
                Quiz.user_id == current_user.id
            )
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="퀴즈를 찾을 수 없습니다."
            )
        
        return quiz
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[퀴즈 상세 조회] 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/{quiz_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz(
    quiz_id: int,
    request: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    퀴즈 제출 및 채점
    
    사용자 답안을 채점하고 결과를 저장합니다.
    """
    try:
        logger.info(f"[퀴즈 제출] 사용자 {current_user.username}이(가) 퀴즈 ID {quiz_id} 제출")
        
        # 퀴즈 조회
        result = db.execute(
            select(Quiz).where(
                Quiz.id == quiz_id,
                Quiz.user_id == current_user.id
            )
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="퀴즈를 찾을 수 없습니다."
            )
        
        # 채점 및 정답/오답 상세 정보 생성
        correct_answers = 0
        wrong_answers = 0
        detailed_results = []  # 각 문제별 상세 결과
        
        for question in quiz.questions:
            question_id = question.get("id")
            correct_answer = question.get("correctAnswer")
            user_answer = request.user_answers.get(question_id)
            
            is_correct = (user_answer == correct_answer or str(user_answer) == str(correct_answer))
            
            if is_correct:
                correct_answers += 1
            else:
                wrong_answers += 1
            
            # 각 문제별 상세 결과 저장
            detailed_results.append({
                "question_id": question_id,
                "question": question.get("question"),
                "user_answer": user_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "explanation": question.get("explanation"),
            })
        
        total_questions = len(quiz.questions)
        score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        is_passed = score >= 60  # 60점 이상 합격
        
        # Quiz 업데이트 - 첫 제출 시 완료 처리, 매번 최신 점수로 업데이트
        if not quiz.is_completed:
            quiz.is_completed = True
            quiz.completed_at = datetime.utcnow()
            logger.info(f"[퀴즈 저장] Quiz 테이블 첫 완료 처리 - is_completed=True")
        
        # 매번 최신 점수로 업데이트 (재시도 시에도 반영)
        quiz.score = score
        quiz.correct_answers = correct_answers
        quiz.wrong_answers = wrong_answers
        quiz.duration_seconds = request.duration_seconds
        logger.info(f"[퀴즈 저장] Quiz 테이블 점수 업데이트 - score={score}, 정답={correct_answers}/{total_questions}")
        
        # QuizAttempt 기록 (재시도 지원) - 정답/오답 상세 내용 포함
        attempt = QuizAttempt(
            quiz_id=quiz.id,
            score=score,
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            user_answers={
                "answers": request.user_answers,
                "detailed_results": detailed_results  # 정답/오답 상세 정보
            },
            duration_seconds=request.duration_seconds
        )
        
        db.add(attempt)
        db.commit()
        db.refresh(quiz)
        
        logger.info(f"[퀴즈 저장] QuizAttempt 기록 생성 완료 (ID: {attempt.id})")
        logger.info(f"[퀴즈 제출] 채점 및 저장 완료 - 점수: {score}점 (정답: {correct_answers}/{total_questions})")
        logger.info(f"[퀴즈 저장] 정답/오답 상세 정보 {len(detailed_results)}개 문제 저장 완료")
        
        feedback = None
        if score >= 90:
            feedback = "훌륭합니다! 완벽하게 이해하셨네요! 🎉"
        elif score >= 70:
            feedback = "잘하셨습니다! 대부분의 개념을 잘 이해하고 계세요. 👍"
        elif score >= 60:
            feedback = "합격입니다! 조금 더 학습하면 더 좋을 것 같아요. 💪"
        else:
            feedback = "아쉽네요. 다시 한번 복습해보시는 것을 추천드립니다. 📚"
        
        return QuizSubmitResponse(
            quiz_id=quiz.id,
            score=score,
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            is_passed=is_passed,
            feedback=feedback
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[퀴즈 제출] 오류: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 제출 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    퀴즈 삭제
    """
    try:
        logger.info(f"[퀴즈 삭제] 사용자 {current_user.username}이(가) 퀴즈 ID {quiz_id} 삭제 요청")
        
        result = db.execute(
            select(Quiz).where(
                Quiz.id == quiz_id,
                Quiz.user_id == current_user.id
            )
        )
        quiz = result.scalar_one_or_none()
        
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="퀴즈를 찾을 수 없습니다."
            )
        
        db.delete(quiz)
        db.commit()
        
        logger.info(f"[퀴즈 삭제] 퀴즈 ID {quiz_id} 삭제 완료")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[퀴즈 삭제] 오류: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 삭제 중 오류가 발생했습니다: {str(e)}"
        )

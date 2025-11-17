"""
학습 관련 API 엔드포인트
통합 학습 세션 생성 기능 제공
"""

from fastapi import APIRouter, HTTPException, status, Depends, Body
import logging

from app.api.dependencies import get_github_access_token
from app.api.v1.endpoints.repo import get_commit_with_diff, get_repository_by_id
from app.schemas.quiz import QuizGenerationRequest
from app.services.learning_session_service import get_learning_session_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/session")
async def generate_learning_session(
    request: QuizGenerationRequest = Body(...),
    access_token: str = Depends(get_github_access_token)
):
    """
    퀴즈와 코드 리뷰를 한 번에 생성 (토큰 절약)

    **요청 본문:**
    - commitShas: 분석할 커밋 SHA 목록 (형식: "owner/repo:sha" 또는 "repo_id:sha")
    - difficulty: 난이도 (easy, medium, hard)
    - questionCount: 생성할 퀴즈 개수 (3-10)

    **응답:**
    - quiz: 생성된 퀴즈 (questions, metadata)
    - review: AI 코드 리뷰 (summary, quality, suggestions, potentialBugs)
    - commitInfo: 첫 번째 커밋의 상세 정보 (파일 목록)

    이 엔드포인트는 단일 Gemini API 호출로 퀴즈와 리뷰를 동시에 생성하여
    API 비용을 절감하고 응답 속도를 향상시킵니다.
    """
    try:
        logger.info(f"========== 통합 학습 세션 API 요청 ==========")
        logger.info(f"요청 데이터: {request.dict()}")
        logger.info(f"커밋 개수: {len(request.commitShas)}, 난이도: {request.difficulty}")

        # 커밋 상세 정보 수집
        commits_details = []

        for commit_identifier in request.commitShas:
            if ':' in commit_identifier:
                repo_part, sha = commit_identifier.split(':', 1)

                if '/' in repo_part:
                    owner, repo = repo_part.split('/', 1)
                elif repo_part.isdigit():
                    repo_id = int(repo_part)
                    repo_data = get_repository_by_id(access_token, repo_id)
                    if not repo_data:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"저장소 ID {repo_id}를 찾을 수 없습니다."
                        )
                    full_name = repo_data.get("full_name")
                    if not full_name:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="저장소 전체 이름을 확인할 수 없습니다."
                        )
                    owner, repo = full_name.split('/', 1)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"잘못된 커밋 식별자: {commit_identifier}"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"커밋 식별자에 저장소 정보가 없습니다: {commit_identifier}"
                )

            logger.info(f"커밋 정보 가져오기: {owner}/{repo}:{sha[:7]}")
            commit_detail = await get_commit_with_diff(access_token, owner, repo, sha)
            commits_details.append(commit_detail)

        if not commits_details:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효한 커밋 정보를 가져올 수 없습니다."
            )

        # 통합 학습 세션 생성 (단일 Gemini 호출)
        logger.info(f"[통합 세션] Gemini API 단일 호출로 퀴즈 + 리뷰 생성 시작")
        session_service = get_learning_session_service()
        result = await session_service.generate_learning_session(
            commits=commits_details,
            question_count=request.questionCount,
            difficulty=request.difficulty
        )

        logger.info(f"========== 통합 학습 세션 API 응답 ==========")
        logger.info(f"퀴즈: {len(result['quiz'].questions)}개")
        logger.info(f"리뷰 제안: {len(result['review'].suggestions)}개")
        logger.info(f"==========================================")

        # 첫 번째 커밋의 파일 정보도 포함 (프론트엔드 편의)
        return {
            "quiz": result["quiz"],
            "review": result["review"],
            "commitInfo": {
                "sha": commits_details[0].sha,
                "message": commits_details[0].message,
                "author": commits_details[0].author,
                "date": commits_details[0].date,
                "files": commits_details[0].files
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"통합 학습 세션 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"학습 세션 생성 중 오류가 발생했습니다: {str(e)}"
        )

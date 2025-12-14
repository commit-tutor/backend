"""
학습 관련 API 엔드포인트
통합 학습 세션 생성 기능 제공
"""

from fastapi import APIRouter, HTTPException, status, Depends, Body
import logging

from app.api.dependencies import get_github_access_token
from app.api.v1.endpoints.repo import get_commit_with_diff, get_repository_by_id
from app.schemas.quiz import QuizGenerationRequest, TopicExtractionRequest
from app.services.quiz_generator import get_quiz_generator
from app.services.topic_generator import get_topic_generator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/topics")
async def generate_learning_topics(
    request: TopicExtractionRequest = Body(...),
    access_token: str = Depends(get_github_access_token)
):
    """
    커밋에서 학습 가능한 주제 생성

    **요청 본문:**
    - commitShas: 분석할 커밋 SHA 목록 (형식: "owner/repo:sha" 또는 "repo_id:sha")

    **응답:**
    - topics: 생성된 학습 주제 목록 (id, title, description, keywords)
    - metadata: 메타데이터 (총 커밋 수, 생성 시간 등)

    이 엔드포인트는 커밋의 코드 변경사항을 분석하여 학습 가능한 CS 주제를 생성합니다.
    사용자는 생성된 주제 중 하나를 선택하여 해당 주제에 집중한 퀴즈를 생성할 수 있습니다.
    """
    try:
        logger.info(f"========== 주제 생성 API 요청 ==========")
        logger.info(f"요청 데이터: {request.dict()}")
        logger.info(f"커밋 개수: {len(request.commitShas)}")

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

        # 주제 생성
        logger.info(f"[주제 생성] Gemini API 호출로 학습 주제 생성 시작")
        topic_generator = get_topic_generator()
        result = await topic_generator.generate_topics(commits=commits_details)

        logger.info(f"========== 주제 생성 API 응답 ==========")
        logger.info(f"생성된 주제: {len(result.topics)}개")
        logger.info(f"==========================================")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주제 생성 중 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"주제 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/session")
async def generate_learning_session(
    request: QuizGenerationRequest = Body(...),
    access_token: str = Depends(get_github_access_token)
):
    """
    커밋 기반 학습 퀴즈 생성

    **요청 본문:**
    - commitShas: 분석할 커밋 SHA 목록 (형식: "owner/repo:sha" 또는 "repo_id:sha")
    - questionCount: 생성할 퀴즈 개수 (3-10)
    - selectedTopic: 선택된 주제 (선택 시 해당 주제의 전반적 CS 지식 학습)

    **응답:**
    - quiz: 생성된 퀴즈 (questions, metadata)
    - commitInfo: 첫 번째 커밋의 상세 정보 (파일 목록)

    주제를 선택하면 커밋 코드를 참고하여 해당 주제의 전반적인 CS 지식을 학습하는 퀴즈를 생성합니다.
    """
    try:
        logger.info(f"========== 통합 학습 세션 API 요청 ==========")
        logger.info(f"요청 데이터: {request.dict()}")
        logger.info(f"커밋 개수: {len(request.commitShas)}, 문제 수: {request.questionCount}")

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

        # 퀴즈 생성
        topic_info = f" (주제: {request.selectedTopic})" if request.selectedTopic else ""
        logger.info(f"[학습 세션] Gemini API 호출로 퀴즈 생성 시작{topic_info}")
        quiz_generator = get_quiz_generator()
        quiz = await quiz_generator.generate_quiz(
            commits=commits_details,
            question_count=request.questionCount,
            difficulty=request.difficulty,
            selected_topic=request.selectedTopic
        )

        logger.info(f"========== 학습 세션 API 응답 ==========")
        logger.info(f"퀴즈: {len(quiz.questions)}개")
        logger.info(f"==========================================")

        # 첫 번째 커밋의 파일 정보도 포함 (프론트엔드 편의)
        return {
            "quiz": quiz,
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

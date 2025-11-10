"""
학습 관련 API 엔드포인트
퀴즈 생성 및 코드 리뷰 생성 기능 제공
"""

from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import List
import logging

from app.api.dependencies import get_github_access_token
from app.api.v1.endpoints.repo import get_commit_with_diff, get_repository_by_id
from app.schemas.quiz import QuizGenerationRequest, QuizGenerationResponse
from app.schemas.analysis import CodeAnalysisRequest, AIAnalysisResponse
from app.services.quiz_generator import get_quiz_generator
from app.services.code_analyzer import get_code_analyzer
from app.services.learning_session_service import get_learning_session_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/quiz", response_model=QuizGenerationResponse)
async def generate_quiz(
    request: QuizGenerationRequest = Body(...),
    access_token: str = Depends(get_github_access_token)
):
    """
    선택한 커밋들을 기반으로 퀴즈 생성

    **요청 본문:**
    - commitShas: 퀴즈를 생성할 커밋 SHA 목록
    - difficulty: 난이도 (easy, medium, hard)
    - questionCount: 생성할 퀴즈 개수 (3-10)

    **응답:**
    - questions: 생성된 퀴즈 목록
    - metadata: 메타데이터 (생성 시간, 커밋 개수 등)

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """
    try:
        logger.info(f"========== 퀴즈 생성 API 요청 ==========")
        logger.info(f"요청 데이터: {request.dict()}")
        logger.info(f"커밋 개수: {len(request.commitShas)}, 난이도: {request.difficulty}, 문제 개수: {request.questionCount}")

        # 각 커밋의 상세 정보 수집 (diff 포함)
        # 커밋 SHA 형식: "owner/repo:sha" 또는 단순 SHA
        commits_details = []

        for commit_identifier in request.commitShas:
            # 형식 파싱: "owner/repo:sha"
            if ':' in commit_identifier:
                repo_part, sha = commit_identifier.split(':', 1)

                # repo_part가 숫자 ID인지 'owner/repo' 형식인지 확인
                if '/' in repo_part:
                    owner, repo = repo_part.split('/', 1)
                elif repo_part.isdigit():
                    # ID로 저장소 정보 가져오기
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
                        detail=f"잘못된 커밋 식별자 형식: {commit_identifier}. 'owner/repo:sha' 또는 'repo_id:sha' 형식이어야 합니다."
                    )
            else:
                # SHA만 제공된 경우 (첫 번째 커밋의 저장소 사용)
                # 실제로는 프론트엔드에서 전체 식별자를 보내야 함
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"커밋 식별자에 저장소 정보가 없습니다: {commit_identifier}. 'owner/repo:sha' 형식으로 제공해주세요."
                )

            # 커밋 상세 정보 가져오기
            logger.info(f"커밋 정보 가져오기: {owner}/{repo}:{sha[:7]}")
            commit_detail = await get_commit_with_diff(access_token, owner, repo, sha)
            total_patch_length = sum(len(f.patch or "") for f in commit_detail.files)
            logger.info(f"커밋 정보 수신: message='{commit_detail.message[:50]}...', files={len(commit_detail.files)}, total_patch_length={total_patch_length}")
            commits_details.append(commit_detail)

        if not commits_details:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효한 커밋 정보를 가져올 수 없습니다."
            )

        # 퀴즈 생성
        logger.info(f"퀴즈 생성 시작...")
        quiz_generator = get_quiz_generator()
        quiz_response = await quiz_generator.generate_quiz(
            commits=commits_details,
            question_count=request.questionCount,
            difficulty=request.difficulty
        )

        logger.info(f"========== 퀴즈 생성 API 응답 ==========")
        logger.info(f"생성된 질문 개수: {len(quiz_response.questions)}")
        for i, q in enumerate(quiz_response.questions, 1):
            logger.info(f"질문 {i}: type={q.type}, question='{q.question[:60]}...'")
        logger.info(f"메타데이터: {quiz_response.metadata}")
        logger.info(f"========================================")

        return quiz_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"퀴즈 생성 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"퀴즈 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/review", response_model=AIAnalysisResponse)
async def generate_code_review(
    request: CodeAnalysisRequest = Body(...),
    access_token: str = Depends(get_github_access_token)
):
    """
    단일 커밋에 대한 AI 코드 리뷰 생성

    **요청 본문:**
    - commitSha: 분석할 커밋 SHA (형식: "owner/repo:sha")
    - focusAreas: 집중 분석 영역 (선택, 예: ["security", "performance"])

    **응답:**
    - summary: 코드 변경사항 요약
    - quality: 코드 품질 점수 (readability, performance, security)
    - suggestions: 개선 제안 목록
    - potentialBugs: 잠재적 버그 목록

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """
    try:
        logger.info(f"========== 코드 리뷰 API 요청 ==========")
        logger.info(f"요청 데이터: {request.dict()}")
        logger.info(f"커밋 식별자: {request.commitSha}")

        # 커밋 식별자 파싱
        commit_identifier = request.commitSha

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
                    detail=f"잘못된 커밋 식별자 형식: {commit_identifier}"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"커밋 식별자에 저장소 정보가 없습니다: {commit_identifier}"
            )

        # 커밋 상세 정보 가져오기
        logger.info(f"커밋 정보 가져오기: {owner}/{repo}:{sha[:7]}")
        commit_detail = await get_commit_with_diff(access_token, owner, repo, sha)
        total_patch_length = sum(len(f.patch or "") for f in commit_detail.files)
        logger.info(f"커밋 정보 수신: message='{commit_detail.message[:50]}...', files={len(commit_detail.files)}, total_patch_length={total_patch_length}")

        # 코드 분석 수행
        logger.info(f"코드 분석 시작...")
        code_analyzer = get_code_analyzer()
        analysis_response = await code_analyzer.analyze_commit(
            commit=commit_detail,
            focus_areas=request.focusAreas
        )

        logger.info(f"========== 코드 리뷰 API 응답 ==========")
        logger.info(f"요약: {analysis_response.summary[:100]}...")
        logger.info(f"품질 점수: readability={analysis_response.quality.readability}, performance={analysis_response.quality.performance}, security={analysis_response.quality.security}")
        logger.info(f"제안 개수: {len(analysis_response.suggestions)}")
        logger.info(f"잠재적 버그: {len(analysis_response.potentialBugs)}")
        logger.info(f"========================================")

        return analysis_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"코드 리뷰 생성 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"코드 리뷰 생성 중 오류가 발생했습니다: {str(e)}"
        )


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

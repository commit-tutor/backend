from fastapi import APIRouter, HTTPException, status
from app.schemas.auth import (
    GitHubCallbackRequest,
    UserResponse,
    LoginURLResponse,
    GitHubAccessTokenResponse,
    GitHubUserInfo
)
from app.core.config import settings
import httpx
from datetime import datetime, timedelta
from jose import jwt
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/github/login", response_model=LoginURLResponse)
async def get_github_login_url():
    """
    GitHub OAuth 로그인 URL 반환
    클라이언트는 이 URL로 사용자를 리다이렉트
    """
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub Client ID가 설정되지 않았습니다."
        )

    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        f"&scope=read:user user:email repo"
    )

    return LoginURLResponse(auth_url=auth_url)


@router.post("/github/callback", response_model=UserResponse)
async def github_oauth_callback(request: GitHubCallbackRequest):
    """
    GitHub OAuth 콜백 처리

    Flow:
    1. GitHub에서 받은 authorization code를 access_token으로 교환
    2. access_token으로 GitHub 사용자 정보 조회
    3. 사용자 정보로 JWT 토큰 생성
    4. 사용자 정보와 JWT 토큰 반환
    """

    # 환경 변수 검증
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth 설정이 올바르지 않습니다."
        )

    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Authorization code를 access token으로 교환
            print("GitHub access token 요청 중...")
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                headers={
                    "Accept": "application/json"
                },
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": request.code,
                    "redirect_uri": settings.GITHUB_REDIRECT_URI,
                },
                timeout=10.0
            )

            if token_response.status_code != 200:
                print(f"GitHub token 요청 실패: {token_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GitHub 토큰 요청에 실패했습니다."
                )

            token_data = token_response.json()

            if "error" in token_data:
                print(f"GitHub OAuth error: {token_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth 오류: {token_data.get('error_description', 'Unknown error')}"
                )

            github_access_token = token_data.get("access_token")

            if not github_access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GitHub access token을 받지 못했습니다."
                )

            print("GitHub access token 획득 성공")
            print(github_access_token)


            # Step 2: GitHub 사용자 정보 조회
            print("GitHub 사용자 정보 조회 중...")
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {github_access_token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=10.0
            )

            if user_response.status_code != 200:
                print(f"GitHub 사용자 정보 조회 실패: {user_response.text}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="GitHub 사용자 정보를 가져올 수 없습니다."
                )
            github_user = user_response.json()
            print(f"GitHub 사용자 정보 획득: {github_user.get('login')}")

            # GitHub Access Token은 JWT에 포함되므로 별도 저장 불필요

            # Step 3: 이메일 정보 조회 (별도 API 필요)
            email = github_user.get("email")

            if not email:
                print("이메일 정보 추가 조회 중...")
                email_response = await client.get(
                    "https://api.github.com/user/emails",
                    headers={
                        "Authorization": f"Bearer {github_access_token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    timeout=10.0
                )

                if email_response.status_code == 200:
                    emails = email_response.json()
                    # primary이면서 verified된 이메일 찾기
                    for email_data in emails:
                        if email_data.get("primary") and email_data.get("verified"):
                            email = email_data.get("email")
                            break

                    # primary가 없으면 verified된 첫 번째 이메일
                    if not email:
                        for email_data in emails:
                            if email_data.get("verified"):
                                email = email_data.get("email")
                                break

            # Step 4: JWT 토큰 생성 (GitHub Access Token 포함)
            jwt_payload = {
                "sub": str(github_user["id"]),  # subject: 사용자 ID
                "username": github_user["login"],
                "email": email,
                "github_access_token": github_access_token,  # GitHub API 호출용 토큰
                "iat": datetime.utcnow(),  # issued at
                "exp": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            }

            jwt_token = jwt.encode(
                jwt_payload,
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM
            )

            print("JWT 토큰 생성 완료")


            # Step 5: 사용자 응답 생성
            # TODO: DB에서 사용자 프로필 조회하여 needs_onboarding 판단
            # 지금은 임시로 항상 True
            needs_onboarding = True

            return UserResponse(
                id=str(github_user["id"]),
                username=github_user["login"],
                email=email,
                avatar_url=github_user["avatar_url"],
                github_token=jwt_token,
                needs_onboarding=needs_onboarding
            )

        except httpx.TimeoutException:
            print("GitHub API 요청 타임아웃")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="GitHub API 요청 시간이 초과되었습니다."
            )
        except httpx.HTTPError as e:
            print(f"HTTP error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"네트워크 오류가 발생했습니다: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"서버 오류가 발생했습니다: {str(e)}"
            )


@router.get("/me")
async def get_current_user():
    """
    현재 로그인한 사용자 정보 조회
    TODO: JWT 토큰 검증 및 사용자 정보 반환
    """
    return {"message": "Not implemented yet"}

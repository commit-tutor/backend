from pydantic import BaseModel, Field
from typing import Optional


class GitHubCallbackRequest(BaseModel):
    """GitHub OAuth 콜백에서 받는 요청"""
    code: str = Field(..., description="GitHub에서 받은 authorization code")


class GitHubAccessTokenResponse(BaseModel):
    """GitHub OAuth access token 응답"""
    access_token: str
    token_type: str
    scope: str


class GitHubUserInfo(BaseModel):
    """GitHub API에서 받은 사용자 정보"""
    id: int
    login: str
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: str
    html_url: str


class UserResponse(BaseModel):
    """클라이언트로 반환하는 사용자 정보"""
    id: str = Field(..., description="사용자 고유 ID")
    username: str = Field(..., description="GitHub username")
    email: Optional[str] = Field(None, description="사용자 이메일")
    avatar_url: str = Field(..., description="프로필 이미지 URL")
    github_token: str = Field(..., description="JWT 토큰")
    needs_onboarding: bool = Field(default=True, description="온보딩 필요 여부")


class LoginURLResponse(BaseModel):
    """GitHub 로그인 URL 응답"""
    auth_url: str = Field(..., description="GitHub OAuth 인증 URL")

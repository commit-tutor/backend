# API dependencies
from fastapi import Header, HTTPException, status
from jose import jwt, JWTError
from typing import Optional
from app.core.config import settings


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    JWT 토큰에서 현재 사용자 ID를 추출합니다.

    Args:
        authorization: Authorization 헤더 (Bearer {token})

    Returns:
        str: GitHub 사용자 ID

    Raises:
        HTTPException: 인증 실패 시
    """
    # Authorization 헤더 누락 체크
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더가 필요합니다. 'Authorization: Bearer <token>' 형식으로 JWT 토큰을 전달해주세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Bearer 토큰 추출
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더 형식이 올바르지 않습니다. 'Bearer <token>' 형식이어야 합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")

    try:
        # JWT 토큰 검증 및 디코딩
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        return user_id

    except JWTError as e:
        print(f"JWT 검증 실패: {e}")
        raise credentials_exception


async def get_github_access_token(authorization: Optional[str] = Header(None)) -> str:
    """
    JWT 토큰에서 GitHub Access Token을 추출합니다.

    Args:
        authorization: Authorization 헤더 (Bearer {token})

    Returns:
        str: GitHub Access Token

    Raises:
        HTTPException: 인증 실패 또는 토큰을 찾을 수 없는 경우
    """
    # Authorization 헤더 누락 체크
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더가 필요합니다. 'Authorization: Bearer <token>' 형식으로 JWT 토큰을 전달해주세요.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더 형식이 올바르지 않습니다. 'Bearer <token>' 형식이어야 합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.replace("Bearer ", "")

    try:
        # JWT 토큰 검증 및 디코딩
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # JWT에서 GitHub Access Token 추출
        github_access_token: str = payload.get("github_access_token")

        if not github_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT에 GitHub 액세스 토큰이 포함되어 있지 않습니다. 다시 로그인해주세요.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return github_access_token

    except JWTError as e:
        print(f"JWT 검증 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

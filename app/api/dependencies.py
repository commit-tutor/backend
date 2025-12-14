# API dependencies
from fastapi import Header, HTTPException, status, Depends
from jose import jwt, JWTError
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.db.database import get_db
from app.models.user import User


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
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


def get_github_access_token(authorization: Optional[str] = Header(None)) -> str:
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


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    JWT 토큰에서 현재 사용자를 가져옵니다.
    사용자가 DB에 없으면 생성합니다.

    Args:
        authorization: Authorization 헤더 (Bearer {token})
        db: 데이터베이스 세션

    Returns:
        User: 현재 사용자 객체

    Raises:
        HTTPException: 인증 실패 시
    """
    # Authorization 헤더 검증
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더가 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization 헤더 형식이 올바르지 않습니다.",
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

        # JWT에서 사용자 정보 추출
        github_id_str = payload.get("sub")
        username = payload.get("username")
        email = payload.get("email")

        if not github_id_str or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT에 필수 사용자 정보가 없습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        github_id = int(github_id_str)

        # 데이터베이스에서 사용자 조회 (동기 방식)
        result = db.execute(
            select(User).where(User.github_id == github_id)
        )
        user = result.scalar_one_or_none()

        # 사용자가 없으면 생성
        if not user:
            user = User(
                github_id=github_id,
                username=username,
                email=email,
                avatar_url=payload.get("avatar_url"),
                needs_onboarding=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user

    except JWTError as e:
        print(f"JWT 검증 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        print(f"GitHub ID 변환 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자 ID가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

"""
데이터베이스 연결 설정
SQLAlchemy Session을 사용한 동기 PostgreSQL 연결
Lazy initialization으로 환경 변수가 없을 때도 앱이 시작될 수 있도록 함
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from app.core.config import settings
from typing import Optional

# 전역 변수 (lazy initialization)
_engine: Optional[any] = None
_SessionLocal: Optional[sessionmaker] = None

# Base 클래스 (모든 모델의 부모 클래스)
Base = declarative_base()


def get_engine():
    """
    데이터베이스 엔진을 lazy하게 생성
    처음 호출될 때만 엔진을 생성하여 환경 변수 오류를 지연시킴
    """
    global _engine
    if _engine is None:
        try:
            database_url = settings.database_url
            _engine = create_engine(
                database_url,
                echo=True,  # SQL 쿼리 로깅 (개발 환경)
                pool_pre_ping=True,  # 연결 상태 확인
                pool_size=1,  # Session Pooler 사용 시 클라이언트 풀 최소화
                max_overflow=0,  # Session Pooler가 연결 관리를 담당
            )
        except ValueError as e:
            # 환경 변수가 설정되지 않은 경우 명확한 에러 메시지
            raise RuntimeError(
                f"Failed to initialize database: {str(e)}\n"
                "This error occurs when database environment variables are not configured."
            ) from e
    return _engine


def get_session_local():
    """세션 팩토리를 lazy하게 생성"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_db() -> Session:
    """
    데이터베이스 세션 의존성
    FastAPI Depends에서 사용
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    데이터베이스 초기화 (테이블 생성)
    개발 환경에서만 사용 - 프로덕션에서는 Alembic 사용
    """
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def test_connection():
    """
    데이터베이스 연결 테스트
    """
    try:
        engine = get_engine()
        with engine.connect() as connection:
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False

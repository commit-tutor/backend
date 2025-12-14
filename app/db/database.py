"""
데이터베이스 연결 설정
AsyncSession을 사용한 비동기 PostgreSQL 연결
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # SQL 쿼리 로깅 (개발 환경)
    future=True,
    pool_pre_ping=True,  # 연결 상태 확인
)

# 세션 팩토리
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base 클래스 (모든 모델의 부모 클래스)
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    데이터베이스 세션 의존성
    FastAPI Depends에서 사용
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    데이터베이스 초기화 (테이블 생성)
    개발 환경에서만 사용 - 프로덕션에서는 Alembic 사용
    """
    async with engine.begin() as conn:
        # 모든 테이블 생성
        await conn.run_sync(Base.metadata.create_all)

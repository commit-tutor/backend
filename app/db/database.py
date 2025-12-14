"""
데이터베이스 연결 설정
SQLAlchemy Session을 사용한 동기 PostgreSQL 연결
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from app.core.config import settings

# 데이터베이스 엔진 생성
# Session Pooler 사용 시 클라이언트 측 풀링을 최소화
engine = create_engine(
    settings.database_url,
    echo=True,  # SQL 쿼리 로깅 (개발 환경)
    pool_pre_ping=True,  # 연결 상태 확인
    pool_size=1,  # Session Pooler 사용 시 클라이언트 풀 최소화
    max_overflow=0,  # Session Pooler가 연결 관리를 담당
)

# 세션 팩토리
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base 클래스 (모든 모델의 부모 클래스)
Base = declarative_base()


def get_db() -> Session:
    """
    데이터베이스 세션 의존성
    FastAPI Depends에서 사용
    """
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
    Base.metadata.create_all(bind=engine)


def test_connection():
    """
    데이터베이스 연결 테스트
    """
    try:
        with engine.connect() as connection:
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return False

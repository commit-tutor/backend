from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1 import api_router
from app.core.config import settings
from app.db.database import test_connection
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작 및 종료 시 실행되는 이벤트
    """
    # Startup
    logger.info("🚀 Starting Commit Tutor API...")
    logger.info(f"📊 Database URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'Not configured'}")
    
    # 데이터베이스 연결 테스트
    if test_connection():
        logger.info("✅ Database connection verified")
    else:
        logger.warning("⚠️  Database connection failed - check your .env settings")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Commit Tutor API...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS 설정
# 프로덕션 환경에서도 안전하게 동작하도록 설정
cors_origins = settings.cors_origins

# 디버깅을 위한 로그
import logging
logger = logging.getLogger(__name__)
logger.info(f"CORS allowed origins: {cors_origins}")
logger.info(f"DEBUG mode: {settings.DEBUG}")

# 개발 환경에서는 로컬 호스트의 모든 포트를 허용하도록 처리
# (실제로는 "*"를 사용할 수 없으므로 common ports 포함)
if settings.DEBUG:
    # 개발 환경: 로컬 호스트 패턴 추가
    localhost_origins = [
        "http://localhost:5174",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5176",
    ]
    # 중복 제거하면서 합치기
    combined_origins = list(set(cors_origins + localhost_origins))
    cors_origins = combined_origins
    logger.info(f"DEBUG mode: Extended CORS origins to {cors_origins}")

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,  # JWT 인증을 위해 필요
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # preflight 요청 캐시 시간 (1시간)
)

# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": "Commit Tutor API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

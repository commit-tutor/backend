from fastapi import APIRouter
from app.api.v1.endpoints import commits, auth

api_router = APIRouter()

# 엔드포인트 등록
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(commits.router, prefix="/commits", tags=["commits"])

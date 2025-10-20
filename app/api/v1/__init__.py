from fastapi import APIRouter
from app.api.v1.endpoints import commits

api_router = APIRouter()

# 엔드포인트 등록
api_router.include_router(commits.router, prefix="/commits", tags=["commits"])

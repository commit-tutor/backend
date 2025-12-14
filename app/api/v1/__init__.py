from fastapi import APIRouter
from app.api.v1.endpoints import commits, auth, repo, learning, my_quiz, review

api_router = APIRouter()

# 엔드포인트 등록
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(commits.router, prefix="/commits", tags=["commits"])
api_router.include_router(repo.router, prefix="/repo", tags=["repo"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(my_quiz.router, prefix="/my-quiz", tags=["my-quiz"])
api_router.include_router(review.router, prefix="/review", tags=["review"])

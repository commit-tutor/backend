from fastapi import APIRouter, HTTPException
from typing import List
from app.schemas.commit import CommitCreate, CommitResponse, CommitAnalysis

router = APIRouter()


@router.post("/analyze", response_model=CommitAnalysis)
async def analyze_commit(commit: CommitCreate):
    """
    커밋 메시지를 분석하고 피드백을 제공합니다.
    """
    # TODO: AI 분석 로직 구현
    return CommitAnalysis(
        message=commit.message,
        score=85,
        suggestions=[
            "커밋 메시지가 명확합니다.",
            "변경 사항을 구체적으로 설명해주세요."
        ],
        category="feature"
    )


@router.get("/history", response_model=List[CommitResponse])
async def get_commit_history(limit: int = 10):
    """
    커밋 히스토리를 조회합니다.
    """
    # TODO: 데이터베이스에서 커밋 히스토리 조회
    return []


@router.get("/{commit_id}", response_model=CommitResponse)
async def get_commit(commit_id: str):
    """
    특정 커밋 정보를 조회합니다.
    """
    # TODO: 데이터베이스에서 커밋 조회
    raise HTTPException(status_code=404, detail="Commit not found")

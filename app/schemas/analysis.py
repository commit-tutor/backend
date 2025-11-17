"""
코드 분석 관련 스키마 정의
프론트엔드 AIAnalysis 인터페이스와 일치하는 구조
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class CodeQuality(BaseModel):
    """코드 품질 메트릭"""
    readability: int = Field(..., description="가독성 점수 (0-100)", ge=0, le=100)
    performance: int = Field(..., description="성능 점수 (0-100)", ge=0, le=100)
    security: int = Field(..., description="보안 점수 (0-100)", ge=0, le=100)


class AIAnalysisResponse(BaseModel):
    """AI 코드 분석 응답 스키마"""
    summary: str = Field(..., description="코드 변경사항 요약")
    quality: CodeQuality = Field(..., description="코드 품질 평가")
    suggestions: List[str] = Field(..., description="개선 제안 목록")
    potentialBugs: List[str] = Field(..., description="잠재적 버그 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "summary": "JWT 토큰 생성 방식을 표준 라이브러리로 변경하여 보안성을 강화했습니다.",
                "quality": {
                    "readability": 85,
                    "performance": 90,
                    "security": 75
                },
                "suggestions": [
                    "SECRET_KEY를 환경 변수로 분리하여 하드코딩을 방지하세요.",
                    "토큰 만료 시간을 설정하여 보안을 강화하세요.",
                    "에러 핸들링을 추가하여 토큰 생성 실패 시 적절히 처리하세요."
                ],
                "potentialBugs": [
                    "SECRET_KEY가 코드에 하드코딩되어 있어 보안 위험이 있습니다.",
                    "payload 검증 로직이 없어 잘못된 데이터가 들어올 수 있습니다."
                ]
            }
        }


class CommitDiffInfo(BaseModel):
    """커밋 diff 상세 정보"""
    filename: str = Field(..., description="파일명")
    status: str = Field(..., description="변경 타입 (added, modified, removed, renamed)")
    additions: int = Field(..., description="추가된 라인 수")
    deletions: int = Field(..., description="삭제된 라인 수")
    patch: Optional[str] = Field(None, description="diff 패치 내용")

    class Config:
        json_schema_extra = {
            "example": {
                "filename": "src/auth/token.py",
                "status": "modified",
                "additions": 5,
                "deletions": 3,
                "patch": "@@ -10,3 +10,5 @@\n-const token = createToken(payload)\n+const token = jwt.sign(payload, secret)"
            }
        }


class CommitDetailResponse(BaseModel):
    """커밋 상세 정보 응답"""
    sha: str = Field(..., description="커밋 SHA")
    message: str = Field(..., description="커밋 메시지")
    author: str = Field(..., description="작성자")
    date: str = Field(..., description="커밋 날짜")
    filesChanged: int = Field(..., description="변경된 파일 개수")
    additions: int = Field(..., description="전체 추가된 라인 수")
    deletions: int = Field(..., description="전체 삭제된 라인 수")
    files: List[CommitDiffInfo] = Field(..., description="변경된 파일 목록")

    class Config:
        json_schema_extra = {
            "example": {
                "sha": "abc123def456",
                "message": "feat: Add JWT authentication",
                "author": "developer",
                "date": "2025-01-09",
                "filesChanged": 2,
                "additions": 15,
                "deletions": 8,
                "files": [
                    {
                        "filename": "src/auth/token.py",
                        "status": "modified",
                        "additions": 10,
                        "deletions": 5,
                        "patch": "..."
                    }
                ]
            }
        }

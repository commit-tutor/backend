from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "Commit Tutor API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS Settings
    # 배포 환경: 모든 origin 허용 (개발 환경에서는 특정 도메인으로 제한 권장)
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost/commit_tutor"

    # Security Settings
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # GitHub OAuth Settings
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "http://localhost:5174/auth/callback"
    FRONTEND_URL: str = "http://localhost:5174"

    # OpenAI Settings (for future AI features)
    OPENAI_API_KEY: str = ""

    # Gemini Settings
    GEMINI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

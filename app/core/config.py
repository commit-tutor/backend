from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "Commit Tutor API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS Settings
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5174",
        "http://localhost:5173",
        "https://commit-tutor.vercel.app",
    ]

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

    # Gemini Settings (Legacy - deprecated)
    GEMINI_API_KEY: str = ""
    
    # OpenRouter Settings
    OPENROUTER_API_KEY: str = ""
    
    # 모델 설정
    # 주제 생성용 모델 (창의적인 주제 추출에 적합)
    OPENROUTER_TOPIC_MODEL: str = "openai/gpt-oss-120b:free"
    
    # 퀴즈 생성용 모델 (구조화된 퀴즈 생성에 적합)
    OPENROUTER_QUIZ_MODEL: str = "tngtech/deepseek-r1t2-chimera:free"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

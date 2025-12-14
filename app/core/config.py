from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union, Any
from functools import lru_cache
import os
import json


class Settings(BaseSettings):
    # Project Settings
    PROJECT_NAME: str = "Commit Tutor API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # CORS Settings
    # 환경 변수에서 쉼표로 구분된 문자열, JSON 배열, 또는 리스트로 받을 수 있음
    # 개발 환경: ["*"] (모든 origin 허용)
    # 프로덕션 환경: 구체적인 origin 리스트
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5174",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://commit-tutor.vercel.app",
    ]
    
    # 개발 모드 여부 (환경 변수로 제어 가능)
    DEBUG: bool = True
    
    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Union[List[str], str]:
        """환경 변수에서 받은 값을 그대로 반환 (나중에 파싱)"""
        return v
    
    def _parse_cors_origins(self) -> List[str]:
        """CORS origins를 파싱하여 리스트로 반환"""
        origins = self.BACKEND_CORS_ORIGINS
        
        # 이미 리스트인 경우
        if isinstance(origins, list):
            return origins
        
        # 문자열인 경우 파싱
        if isinstance(origins, str):
            # JSON 배열인 경우
            if origins.strip().startswith('['):
                try:
                    parsed = json.loads(origins)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            
            # 쉼표로 구분된 문자열인 경우
            parsed_list = [origin.strip() for origin in origins.split(',') if origin.strip()]
            if parsed_list:
                return parsed_list
        
        # 기본값 반환 (개발 환경에서 자주 사용되는 포트들 포함)
        return [
            "http://localhost:5174",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "https://commit-tutor.vercel.app",
        ]
    
    @property
    def cors_origins(self) -> List[str]:
        """파싱된 CORS origins 반환"""
        return self._parse_cors_origins()

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
    OPENROUTER_TOPIC_MODEL: str = "openai/gpt-oss-20b:free"
    
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

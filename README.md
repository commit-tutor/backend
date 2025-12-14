# Commit Tutor Backend

FastAPI 기반 백엔드 서버입니다.

## 기술 스택

- FastAPI 0.115.0
- Python 3.11+
- PostgreSQL
- SQLAlchemy
- Pydantic

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 생성하고 다음 환경변수를 설정하세요:

```bash
# Security
SECRET_KEY=your-secret-key-change-this-in-production

# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:5174/auth/callback
FRONTEND_URL=http://localhost:5174

# OpenRouter API (Free AI Models)
# Get your API key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here

# AI 모델 설정 (선택사항 - 기본값 사용)
OPENROUTER_TOPIC_MODEL=openai/gpt-oss-120b:free  # 주제 생성용
OPENROUTER_QUIZ_MODEL=tngtech/deepseek-r1t2-chimera:free  # 퀴즈 생성용

# Database (optional)
DATABASE_URL=postgresql+asyncpg://user:password@localhost/commit_tutor
```

**OpenRouter API 키 발급 방법:**

1. https://openrouter.ai 방문
2. 계정 생성 (무료)
3. https://openrouter.ai/keys 에서 API 키 발급
4. 발급받은 키를 `.env` 파일의 `OPENROUTER_API_KEY`에 설정

**사용 중인 AI 모델:**

- **주제 생성**: `openai/gpt-oss-120b:free` - 창의적인 주제 추출에 최적화
- **퀴즈 생성**: `tngtech/deepseek-r1t2-chimera:free` - 구조화된 퀴즈 생성에 최적화

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 URL에서 확인할 수 있습니다:

- API 문서: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- Health Check: http://localhost:8000/health

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   └── commits.py
│   │       └── __init__.py
│   ├── core/
│   │   └── config.py
│   ├── models/
│   ├── schemas/
│   │   └── commit.py
│   ├── services/
│   └── main.py
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## API 엔드포인트

### Commits

- `POST /api/v1/commits/analyze` - 커밋 메시지 분석
- `GET /api/v1/commits/history` - 커밋 히스토리 조회
- `GET /api/v1/commits/{commit_id}` - 특정 커밋 조회

## 개발

### 테스트 실행

```bash
pytest
```

### 코드 포맷팅

```bash
black app/
isort app/
```

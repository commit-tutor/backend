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
# Database Configuration (Supabase PostgreSQL - Session Pooler)
# 방법 1: 개별 설정 (권장 - Session Pooler 사용)
DB_USER=postgres.mdqpzwhhbpmcvcxvjhld
DB_PASSWORD=your_supabase_password_here
DB_HOST=aws-1-ap-northeast-1.pooler.supabase.com
DB_PORT=5432
DB_NAME=postgres

# 방법 2: 전체 URL 사용 (위의 개별 설정이 우선순위)
# DATABASE_URL=postgresql+psycopg2://postgres.mdqpzwhhbpmcvcxvjhld:password@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require

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

# Debug Mode
DEBUG=True
```

**Supabase 데이터베이스 설정 방법 (Session Pooler):**

1. Supabase 대시보드 (https://supabase.com/dashboard) 접속
2. 프로젝트 선택 → Settings → Database
3. Connection string 섹션에서 **"Session Pooler"** 선택
4. User, Password, Host 정보를 `.env` 파일에 입력
   - User: `postgres.{프로젝트ID}` 형식
   - Host: `aws-{region}.pooler.supabase.com` 형식

**Session Pooler 장점:**
- 서버 측에서 연결 풀링 관리
- 동시 연결 수 최적화
- 더 나은 성능과 안정성

**데이터베이스 연결 테스트:**

```bash
python test_db_connection.py
```

이 스크립트는 데이터베이스 연결 상태, PostgreSQL 버전, 기존 테이블 목록을 확인합니다.

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

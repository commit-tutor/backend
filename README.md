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

```bash
cp .env.example .env
# .env 파일을 열어 필요한 값들을 설정하세요
```

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

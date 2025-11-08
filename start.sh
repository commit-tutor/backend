#!/bin/bash

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PORT=8000

echo -e "${YELLOW}Checking for processes running on port ${PORT}...${NC}"

# port 8000을 사용 중인 프로세스 찾기
PID=$(lsof -ti:${PORT})

if [ -n "$PID" ]; then
    echo -e "${YELLOW}Found process(es) using port ${PORT}: ${PID}${NC}"
    echo -e "${YELLOW}Killing process(es)...${NC}"
    kill -9 $PID
    echo -e "${GREEN}Process(es) killed successfully${NC}"
    sleep 1
else
    echo -e "${GREEN}No process found using port ${PORT}${NC}"
fi

# 가상환경 활성화
if [ -d ".venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source .venv/bin/activate
else
    echo -e "${RED}Virtual environment not found! Please create one first.${NC}"
    echo -e "${YELLOW}Run: python -m venv .venv${NC}"
    exit 1
fi

# FastAPI 서버 시작
echo -e "${GREEN}Starting FastAPI server on port ${PORT}...${NC}"
uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --reload

# db/temporary_storage.py (임시 DB 역할)
from typing import Dict, Optional

# Key: GitHub User ID (str), Value: GitHub Access Token (str)
TEMP_GITHUB_TOKEN_STORE: Dict[str, str] = {}

def save_github_token_temp(github_id: str, access_token: str):
    """Access Token을 메모리 내 딕셔너리에 저장합니다."""
    TEMP_GITHUB_TOKEN_STORE[github_id] = access_token
    print(f"✅ Token for user {github_id} temporarily saved.")

def get_github_token_temp(github_id: str) -> Optional[str]:
    """저장된 Access Token을 불러옵니다."""
    return TEMP_GITHUB_TOKEN_STORE.get(github_id)
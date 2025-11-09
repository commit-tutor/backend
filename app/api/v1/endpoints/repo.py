# github_api.py
import random
from fastapi import APIRouter, HTTPException, status, Query, Depends
from datetime import datetime
import requests
from typing import List, Dict, Any, Optional
import json
import asyncio
import httpx

from app.api.dependencies import get_github_access_token
from app.schemas.analysis import CommitDetailResponse, CommitDiffInfo

router = APIRouter()

GITHUB_API_BASE_URL = "https://api.github.com"

# Safety settings for external GitHub requests
REQUEST_TIMEOUT_SECONDS = 10
MAX_PAGINATION_PAGES = 10

def get_user_repositories(access_token: str) -> List[Dict[str, Any]]:
    """
    GitHub Access Token을 사용하여 인증된 사용자의 저장소 목록을 가져옵니다.
    """
    
    # HTTP 헤더에 Access Token을 Bearer 방식으로 포함합니다.
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    repos_endpoint = f"{GITHUB_API_BASE_URL}/user/repos"
    
    # 쿼리 파라미터 (최대 페이지당 100개, 첫 페이지부터 시작)
    params = {
        "per_page": 100,
        "page": 1,
        "type": "all" # 사용자가 접근 가능한 모든 레포지토리를 가져옵니다.
    }
    
    all_repos = []

    page_count = 0
    while True:
        try:
            response = requests.get(repos_endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status() # 200 외의 응답 코드는 예외 발생

            current_repos = response.json()
            if not current_repos:
                break # 더 이상 저장소가 없으면 종료

            all_repos.extend(current_repos)
            
            # 다음 페이지가 있는지 확인하는 로직 (GitHub API의 Pagination 방식)
            # Link 헤더를 파싱하거나, 단순히 페이지 번호를 증가시켜 시도합니다.
            
            # 여기서는 간단하게 페이지 번호만 증가시켜 다음 요청을 준비합니다.
            params["page"] += 1
            page_count += 1
            if page_count >= MAX_PAGINATION_PAGES:
                break
            
            # (💡 참고: 정확한 처리를 위해서는 response.headers['Link']를 파싱해야 합니다.)

        except requests.exceptions.Timeout:
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="GitHub API timeout while fetching repositories")
        except requests.exceptions.HTTPError as e:
            print(f"GitHub API 요청 실패: {e}")
            # 에러 발생 시 현재까지 가져온 목록만 반환하거나 예외를 다시 발생시킬 수 있습니다.
            break
        except Exception as e:
            print(f"예외 발생: {e}")
            break
    return all_repos

def process_repositories_data(raw_repos_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    GitHub 저장소 목록 JSON에서 필요한 핵심 정보만 추출하여 가공하고 최신순으로 정렬합니다.
    """
    processed_list = []

    for repo in raw_repos_list:
        # Commit Tutor 프로젝트에 중요한 핵심 필드만 추출
        processed_repo = {
            "id": repo.get("id"),
            "name": repo.get("name"),                               # 저장소 이름
            "full_name": repo.get("full_name"),                     # 소유자/이름 (API 호출에 유용)
            "owner_login": repo.get("owner", {}).get("login"),      # 소유자 이름
            "private": repo.get("private"),                         # 비공개 여부 (True/False)
            "fork": repo.get("fork"),                               # 포크된 저장소 여부
            "description": repo.get("description"),                 # 설명
            "language": repo.get("language"),                       # 주 언어
            "default_branch": repo.get("default_branch", "main"),   # 기본 브랜치 (커밋 조회 시 필요)
            "updated_at": repo.get("updated_at"),                   # 최종 업데이트 시각
        }

        # 포크된 저장소는 보통 사용자가 직접 커밋하는 대상이 아니므로 제외 (선택 사항)
        # 만약 직접 포크 저장소에 커밋하는 경우를 허용하려면 이 필터를 제거하세요.
        # if not processed_repo["fork"]:
        processed_list.append(processed_repo)

    # 최신 업데이트 순으로 정렬 (updated_at 기준 내림차순)
    processed_list.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

    return processed_list
def get_repository_by_id(access_token: str, repo_id: int) -> Optional[Dict[str, Any]]:
    """
    GitHub Repository ID를 사용하여 저장소의 상세 정보를 가져옵니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # API 엔드포인트: /repositories/{id} (일반 저장소 상세 조회)
    details_endpoint = f"{GITHUB_API_BASE_URL}/repositories/{repo_id}"
    
    try:
        response = requests.get(details_endpoint, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError as e:
        print(f"GitHub Repository ID API 요청 실패 (ID: {repo_id}): {e}")
        # 404일 경우 None 반환
        return None
    except Exception as e:
        print(f"예외 발생: {e}")
        return None

def get_commit_details(access_token: str, owner: str, repo: str, commit_sha: str) -> Optional[Dict[str, Any]]:
    """
    특정 커밋의 상세 내역 (파일 변경, 추가/삭제 라인 수)을 가져옵니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    # 커밋 상세 API 엔드포인트: /repos/{owner}/{repo}/commits/{commit_sha}
    details_endpoint = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/commits/{commit_sha}"

    try:
        response = requests.get(details_endpoint, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.HTTPError as e:
        print(f"GitHub Commit Detail API 요청 실패 (SHA: {commit_sha}): {e}")
        return None
    except Exception as e:
        print(f"예외 발생: {e}")
        return None

async def get_commit_details_async(client: httpx.AsyncClient, access_token: str, owner: str, repo: str, commit_sha: str) -> Optional[Dict[str, Any]]:
    """
    비동기로 특정 커밋의 상세 내역을 가져옵니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    details_endpoint = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/commits/{commit_sha}"

    try:
        response = await client.get(details_endpoint, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        print(f"타임아웃: {commit_sha}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"GitHub Commit Detail API 요청 실패 (SHA: {commit_sha}): {e}")
        return None
    except Exception as e:
        print(f"예외 발생: {e}")
        return None

def get_repository_commits(access_token: str, owner: str, repo: str, branch: str, per_page: int = 100) -> List[Dict[str, Any]]:
    """
    특정 저장소의 특정 브랜치 커밋 내역 목록을 가져옵니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    commits_endpoint = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/commits"
    
    params = {
        "sha": branch,      # 브랜치 이름으로 필터링
        "per_page": per_page,
        "page": 1,
    }
    
    all_commits = []

    try:
        response = requests.get(commits_endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        
        # 실제로는 Link 헤더를 이용해 페이지네이션 처리 필요
        all_commits.extend(response.json())
        
        return all_commits
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="GitHub API timeout while fetching commits")
    except requests.exceptions.HTTPError as e:
        print(f"GitHub Commit API 요청 실패: {e}")
        raise HTTPException(status_code=response.status_code, detail="GitHub API에서 커밋 정보를 가져오는 데 실패했습니다.")
    except Exception as e:
        print(f"예외 발생: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="서버 오류 발생")

def process_commits_data(access_token: str, owner: str, repo: str, raw_commits_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    GitHub 커밋 목록 JSON을 프론트엔드 형식에 맞게 가공하고 상세 정보를 추가합니다.
    """
    processed_list = []

    learning_values: List[str] = ['high', 'medium', 'low']

    for commit_data in raw_commits_list:
        sha = commit_data.get('sha')
        commit_info = commit_data.get('commit', {})
        author_info = commit_info.get('author', {})

        # 1. 상세 정보 가져오기 (파일 변경, 추가/삭제 라인 수)
        details = get_commit_details(access_token, owner, repo, sha)

        files_changed = 0
        additions = 0
        deletions = 0

        if details and 'stats' in details:
            # filesChanged는 'files' 목록의 길이
            files_changed = len(details.get('files', []))
            # additions, deletions은 'stats' 객체에서 가져옵니다.
            stats = details['stats']
            additions = stats.get('additions', 0)
            deletions = stats.get('deletions', 0)

        # 2. 날짜 포맷팅
        raw_date_str = author_info.get('date')
        formatted_date = raw_date_str
        try:
            dt_object = datetime.strptime(raw_date_str, "%Y-%m-%dT%H:%M:%SZ")
            formatted_date = dt_object.strftime("%Y-%m-%d %H:%M:%S (UTC)")
        except ValueError:
            pass

        # 3. 데이터 가공 및 임시 필드 추가
        processed_commit = {
            "sha": sha,
            "message": commit_info.get('message', '').strip(),
            "author": commit_data.get('author', {}).get('login') or author_info.get('name'), # GitHub ID가 없으면 Git Name 사용
            "date": formatted_date,
            "filesChanged": files_changed,    # 🌟 상세 API 호출 결과
            "additions": additions,          # 🌟 상세 API 호출 결과
            "deletions": deletions,          # 🌟 상세 API 호출 결과
            "learningValue": random.choice(learning_values), # 💡 임시 값
            "isCompleted": random.choice([True, False, False]), # 💡 임시 값
        }

        processed_list.append(processed_commit)

    return processed_list

async def process_commits_data_async(access_token: str, owner: str, repo: str, raw_commits_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    비동기로 GitHub 커밋 목록을 처리하고 상세 정보를 병렬로 가져옵니다.
    """
    learning_values: List[str] = ['high', 'medium', 'low']

    async with httpx.AsyncClient() as client:
        # 모든 커밋의 상세 정보를 병렬로 가져오기
        tasks = []
        for commit_data in raw_commits_list:
            sha = commit_data.get('sha')
            task = get_commit_details_async(client, access_token, owner, repo, sha)
            tasks.append((commit_data, task))

        # 병렬 실행
        results = await asyncio.gather(*[task for _, task in tasks])

        # 결과 처리
        processed_list = []
        for idx, commit_data in enumerate(raw_commits_list):
            sha = commit_data.get('sha')
            commit_info = commit_data.get('commit', {})
            author_info = commit_info.get('author', {})

            # 상세 정보
            details = results[idx]
            files_changed = 0
            additions = 0
            deletions = 0

            if details and 'stats' in details:
                files_changed = len(details.get('files', []))
                stats = details['stats']
                additions = stats.get('additions', 0)
                deletions = stats.get('deletions', 0)

            # 날짜 포맷팅
            raw_date_str = author_info.get('date')
            formatted_date = raw_date_str
            try:
                dt_object = datetime.strptime(raw_date_str, "%Y-%m-%dT%H:%M:%SZ")
                formatted_date = dt_object.strftime("%Y-%m-%d %H:%M:%S (UTC)")
            except ValueError:
                pass

            # 데이터 가공
            processed_commit = {
                "sha": sha,
                "message": commit_info.get('message', '').strip(),
                "author": commit_data.get('author', {}).get('login') or author_info.get('name'),
                "date": formatted_date,
                "filesChanged": files_changed,
                "additions": additions,
                "deletions": deletions,
                "learningValue": random.choice(learning_values),
                "isCompleted": random.choice([True, False, False]),
            }

            processed_list.append(processed_commit)

    return processed_list


# print(json.dumps(clean_repos, indent=4, ensure_ascii=False))

# print(json.dumps(clean_commits, indent=4, ensure_ascii=False))

@router.get("/get_repo")
async def get_user_repo(access_token: str = Depends(get_github_access_token)):
    """
    현재 로그인한 사용자의 GitHub 저장소 목록을 반환합니다.

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """
    raw_repos = get_user_repositories(access_token=access_token)
    clean_repos = process_repositories_data(raw_repos)
    return clean_repos

@router.get("/{repo_identifier}/commits")
async def get_repo_commits_for_frontend(
    repo_identifier: str, # 경로에서 숫자 ID 또는 'owner/repo' 형태의 전체 이름을 받습니다.
    branch: str = Query("main", description="조회할 브랜치 이름"),
    access_token: str = Depends(get_github_access_token)
):
    """
    특정 저장소의 커밋 목록을 프론트엔드에 필요한 형식으로 반환합니다.

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """
    
    owner = None
    repo = None

    # 1. 식별자가 숫자인지 확인 (프론트엔드에서 Repo ID를 보낼 경우)
    if repo_identifier.isdigit():
        repo_id = int(repo_identifier)
        repo_data = get_repository_by_id(access_token, repo_id)
        
        if not repo_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"ID {repo_id}에 해당하는 저장소를 찾을 수 없습니다. (권한 문제 또는 존재하지 않는 ID)"
            )
        
        repo_full_name = repo_data.get('full_name')
        if not repo_full_name:
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"저장소 정보에서 전체 이름(full_name)을 추출할 수 없습니다."
            )
        # full_name에서 owner와 repo 이름 분리 (예: 'MoonYoung02/CommitTutor')
        owner, repo = repo_full_name.split('/', 1)
    
    # 2. 식별자가 'owner/repo' 형식인지 확인 (직접 full_name을 보낼 경우)
    elif '/' in repo_identifier:
        try:
            owner, repo = repo_identifier.split('/', 1)
        except ValueError:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"잘못된 저장소 식별자 형식입니다. 숫자 ID 또는 'owner/repo' 형식이어야 합니다. 현재: {repo_identifier}"
            )
    else:
        # 이도 저도 아닌 경우 처리
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"인식할 수 없는 저장소 식별자 형식입니다. 현재: {repo_identifier}"
        )


    # 3. 커밋 목록 가져오기
    raw_commits = get_repository_commits(access_token=access_token, owner=owner, repo=repo, branch=branch, per_page=20)

    # 4. 상세 정보 포함하여 프론트엔드 형식으로 가공 (비동기 병렬 처리)
    clean_commits = await process_commits_data_async(access_token=access_token, owner=owner, repo=repo, raw_commits_list=raw_commits)

    return clean_commits


def get_repository_branches(access_token: str, owner: str, repo: str, per_page: int = 100) -> List[Dict[str, Any]]:
    """
    저장소의 브랜치 목록을 반환합니다.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    branches_endpoint = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/branches"

    params = {
        "per_page": per_page,
        "page": 1,
    }

    try:
        response = requests.get(branches_endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="GitHub API timeout while fetching branches")
    except requests.exceptions.HTTPError as e:
        print(f"GitHub Branches API 요청 실패: {e}")
        raise HTTPException(status_code=response.status_code, detail="GitHub API에서 브랜치 정보를 가져오지 못했습니다.")
    except Exception as e:
        print(f"예외 발생: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="서버 오류 발생")


@router.get("/{repo_identifier}/branches")
async def get_repo_branches_for_frontend(
    repo_identifier: str,
    access_token: str = Depends(get_github_access_token)
):
    """
    특정 저장소의 브랜치 목록을 반환합니다. 응답은 브랜치 이름의 리스트입니다.

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """

    # 숫자 ID 또는 'owner/repo' 모두 허용
    if repo_identifier.isdigit():
        repo_id = int(repo_identifier)
        repo_data = get_repository_by_id(access_token, repo_id)
        if not repo_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")
        full_name = repo_data.get("full_name")
        if not full_name:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="저장소 전체 이름(full_name)을 확인할 수 없습니다.")
        owner, repo = full_name.split('/', 1)
    elif '/' in repo_identifier:
        try:
            owner, repo = repo_identifier.split('/', 1)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 저장소 식별자 형식입니다.")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인식할 수 없는 저장소 식별자 형식입니다.")

    raw = get_repository_branches(access_token, owner, repo)
    branch_names = [b.get('name') for b in raw if isinstance(b, dict) and b.get('name')]
    return branch_names


async def get_commit_with_diff(access_token: str, owner: str, repo: str, commit_sha: str) -> CommitDetailResponse:
    """
    커밋의 상세 정보를 diff(patch) 정보와 함께 반환합니다.
    퀴즈 및 리뷰 생성에 필요한 전체 정보를 제공합니다.

    Args:
        access_token: GitHub 액세스 토큰
        owner: 저장소 소유자
        repo: 저장소 이름
        commit_sha: 커밋 SHA

    Returns:
        CommitDetailResponse 객체 (diff 정보 포함)

    Raises:
        HTTPException: 커밋 정보를 가져오지 못한 경우
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    details_endpoint = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/commits/{commit_sha}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(details_endpoint, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()

            data = response.json()

            # 커밋 기본 정보 추출
            commit_info = data.get('commit', {})
            author_info = commit_info.get('author', {})
            stats = data.get('stats', {})
            files_data = data.get('files', [])

            # 날짜 포맷팅
            raw_date_str = author_info.get('date', '')
            formatted_date = raw_date_str
            try:
                dt_object = datetime.strptime(raw_date_str, "%Y-%m-%dT%H:%M:%SZ")
                formatted_date = dt_object.strftime("%Y-%m-%d %H:%M:%S (UTC)")
            except ValueError:
                pass

            # 파일 변경 정보 구성
            files = []
            for file_data in files_data:
                diff_info = CommitDiffInfo(
                    filename=file_data.get('filename', ''),
                    status=file_data.get('status', 'modified'),
                    additions=file_data.get('additions', 0),
                    deletions=file_data.get('deletions', 0),
                    patch=file_data.get('patch')  # diff 패치 내용
                )
                files.append(diff_info)

            # CommitDetailResponse 생성
            commit_detail = CommitDetailResponse(
                sha=data.get('sha', ''),
                message=commit_info.get('message', '').strip(),
                author=data.get('author', {}).get('login') or author_info.get('name', 'Unknown'),
                date=formatted_date,
                filesChanged=len(files_data),
                additions=stats.get('additions', 0),
                deletions=stats.get('deletions', 0),
                files=files
            )

            return commit_detail

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"커밋 {commit_sha} 정보 가져오기 시간 초과"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"커밋 {commit_sha}를 찾을 수 없습니다."
        )
    except Exception as e:
        print(f"커밋 상세 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"커밋 상세 정보 조회 중 오류 발생: {str(e)}"
        )


@router.get("/{repo_identifier}/commits/{commit_sha}/details")
async def get_commit_details_for_learning(
    repo_identifier: str,
    commit_sha: str,
    access_token: str = Depends(get_github_access_token)
) -> CommitDetailResponse:
    """
    특정 커밋의 상세 정보를 diff와 함께 반환합니다.
    퀴즈/리뷰 생성에 사용됩니다.

    인증이 필요한 엔드포인트입니다. Authorization 헤더에 JWT 토큰을 포함해야 합니다.
    """
    # 저장소 식별자 파싱
    if repo_identifier.isdigit():
        repo_id = int(repo_identifier)
        repo_data = get_repository_by_id(access_token, repo_id)
        if not repo_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="저장소를 찾을 수 없습니다.")
        full_name = repo_data.get("full_name")
        if not full_name:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="저장소 전체 이름을 확인할 수 없습니다.")
        owner, repo = full_name.split('/', 1)
    elif '/' in repo_identifier:
        try:
            owner, repo = repo_identifier.split('/', 1)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 저장소 식별자 형식입니다.")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="인식할 수 없는 저장소 식별자 형식입니다.")

    # 커밋 상세 정보 조회
    return await get_commit_with_diff(access_token, owner, repo, commit_sha)

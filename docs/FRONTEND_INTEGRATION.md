# 프론트엔드 연동 가이드

## 1. GitHub 로그인 플로우

### Step 1: 로그인 URL 받기
```javascript
// GET /api/v1/auth/github/login
const response = await fetch('http://localhost:8000/api/v1/auth/github/login');
const { auth_url } = await response.json();

// 사용자를 GitHub OAuth 페이지로 리다이렉트
window.location.href = auth_url;
```

**응답 예시:**
```json
{
  "auth_url": "https://github.com/login/oauth/authorize?client_id=...&redirect_uri=...&scope=read:user user:email repo"
}
```

---

### Step 2: GitHub 콜백 처리
GitHub에서 `redirect_uri`로 돌아올 때 `code` 파라미터를 받습니다.

```javascript
// URL: http://localhost:3000/auth/callback?code=abc123...

// URL에서 code 추출
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');

// POST /api/v1/auth/github/callback
const response = await fetch('http://localhost:8000/api/v1/auth/github/callback', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ code })
});

const userData = await response.json();

// JWT 토큰을 localStorage에 저장 ⭐
localStorage.setItem('jwt_token', userData.github_token);
localStorage.setItem('user_id', userData.id);
localStorage.setItem('username', userData.username);

// 메인 페이지로 이동
window.location.href = '/dashboard';
```

**응답 예시:**
```json
{
  "id": "12345678",
  "username": "your-github-username",
  "email": "your-email@example.com",
  "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
  "github_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "needs_onboarding": true
}
```

---

## 2. 인증이 필요한 API 요청

모든 API 요청 시 **Authorization 헤더에 JWT 토큰**을 포함해야 합니다.

### 방법 1: 매번 헤더 추가 (기본)
```javascript
const jwt_token = localStorage.getItem('jwt_token');

const response = await fetch('http://localhost:8000/api/v1/repo/get_repo', {
  headers: {
    'Authorization': `Bearer ${jwt_token}`
  }
});

const repos = await response.json();
```

---

### 방법 2: Axios 인터셉터 (권장)
매번 헤더를 추가하는 대신, 자동으로 토큰을 추가하도록 설정합니다.

```javascript
// api/client.js
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api/v1'
});

// 요청 인터셉터: 모든 요청에 자동으로 JWT 추가
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 응답 인터셉터: 401 에러 시 로그인 페이지로 이동
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 토큰 만료 또는 유효하지 않음
      localStorage.removeItem('jwt_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

**사용 예시:**
```javascript
// 저장소 목록 조회
const repos = await apiClient.get('/repo/get_repo');

// 커밋 목록 조회
const commits = await apiClient.get('/repo/12345678/commits?branch=main');

// 브랜치 목록 조회
const branches = await apiClient.get('/repo/owner/repo-name/branches');
```

---

## 3. API 엔드포인트 목록

### 3.1 저장소 목록 조회
```
GET /api/v1/repo/get_repo
Authorization: Bearer {jwt_token}
```

**응답:**
```json
[
  {
    "id": 123456789,
    "name": "my-repo",
    "full_name": "username/my-repo",
    "owner_login": "username",
    "private": false,
    "fork": false,
    "description": "My awesome project",
    "language": "Python",
    "default_branch": "main",
    "updated_at": "2025-01-15T10:30:00Z"
  }
]
```

---

### 3.2 커밋 목록 조회
```
GET /api/v1/repo/{repo_identifier}/commits?branch=main
Authorization: Bearer {jwt_token}
```

**파라미터:**
- `repo_identifier`: 저장소 ID (숫자) 또는 `owner/repo` 형식
- `branch`: 브랜치 이름 (기본값: `main`)

**응답:**
```json
[
  {
    "sha": "abc123...",
    "message": "Fix bug in authentication",
    "author": "username",
    "date": "2025-01-15 10:30:00 (UTC)",
    "filesChanged": 3,
    "additions": 25,
    "deletions": 10,
    "learningValue": "high",
    "isCompleted": false
  }
]
```

---

### 3.3 브랜치 목록 조회
```
GET /api/v1/repo/{repo_identifier}/branches
Authorization: Bearer {jwt_token}
```

**응답:**
```json
["main", "develop", "feature/new-auth", "bugfix/login-issue"]
```

---

## 4. React 컴포넌트 예시

### 4.1 로그인 페이지
```jsx
// pages/Login.jsx
import { useEffect } from 'react';
import apiClient from '../api/client';

function Login() {
  const handleLogin = async () => {
    try {
      const { data } = await apiClient.get('/auth/github/login');
      window.location.href = data.auth_url;
    } catch (error) {
      console.error('로그인 실패:', error);
    }
  };

  return (
    <div>
      <h1>Commit Tutor</h1>
      <button onClick={handleLogin}>
        GitHub으로 로그인
      </button>
    </div>
  );
}

export default Login;
```

---

### 4.2 GitHub 콜백 페이지
```jsx
// pages/AuthCallback.jsx
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';

function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    const handleCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');

      if (!code) {
        navigate('/login');
        return;
      }

      try {
        const { data } = await apiClient.post('/auth/github/callback', { code });

        // JWT 토큰 저장
        localStorage.setItem('jwt_token', data.github_token);
        localStorage.setItem('user_id', data.id);
        localStorage.setItem('username', data.username);
        localStorage.setItem('avatar_url', data.avatar_url);

        // 대시보드로 이동
        navigate('/dashboard');
      } catch (error) {
        console.error('인증 실패:', error);
        navigate('/login');
      }
    };

    handleCallback();
  }, [navigate]);

  return <div>로그인 처리 중...</div>;
}

export default AuthCallback;
```

---

### 4.3 저장소 목록 페이지
```jsx
// pages/Repositories.jsx
import { useState, useEffect } from 'react';
import apiClient from '../api/client';

function Repositories() {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const { data } = await apiClient.get('/repo/get_repo');
        setRepos(data);
      } catch (error) {
        console.error('저장소 조회 실패:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchRepos();
  }, []);

  if (loading) return <div>로딩 중...</div>;

  return (
    <div>
      <h1>내 저장소 목록</h1>
      <ul>
        {repos.map((repo) => (
          <li key={repo.id}>
            <h3>{repo.full_name}</h3>
            <p>{repo.description}</p>
            <span>언어: {repo.language}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Repositories;
```

---

### 4.4 커밋 목록 페이지
```jsx
// pages/Commits.jsx
import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import apiClient from '../api/client';

function Commits() {
  const { repoId } = useParams(); // URL: /repos/:repoId/commits
  const [commits, setCommits] = useState([]);
  const [branches, setBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState('main');

  useEffect(() => {
    const fetchBranches = async () => {
      try {
        const { data } = await apiClient.get(`/repo/${repoId}/branches`);
        setBranches(data);
      } catch (error) {
        console.error('브랜치 조회 실패:', error);
      }
    };

    fetchBranches();
  }, [repoId]);

  useEffect(() => {
    const fetchCommits = async () => {
      try {
        const { data } = await apiClient.get(
          `/repo/${repoId}/commits?branch=${selectedBranch}`
        );
        setCommits(data);
      } catch (error) {
        console.error('커밋 조회 실패:', error);
      }
    };

    fetchCommits();
  }, [repoId, selectedBranch]);

  return (
    <div>
      <h1>커밋 목록</h1>

      {/* 브랜치 선택 */}
      <select
        value={selectedBranch}
        onChange={(e) => setSelectedBranch(e.target.value)}
      >
        {branches.map((branch) => (
          <option key={branch} value={branch}>
            {branch}
          </option>
        ))}
      </select>

      {/* 커밋 목록 */}
      <ul>
        {commits.map((commit) => (
          <li key={commit.sha}>
            <h3>{commit.message}</h3>
            <p>작성자: {commit.author}</p>
            <p>날짜: {commit.date}</p>
            <p>
              변경: {commit.filesChanged}개 파일,
              +{commit.additions} -{commit.deletions}
            </p>
            <span>학습 가치: {commit.learningValue}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default Commits;
```

---

## 5. 주의사항

### 5.1 토큰 만료 처리
JWT 토큰은 설정된 시간(기본 60분)이 지나면 만료됩니다. 만료 시:
- 401 Unauthorized 에러 발생
- 사용자를 로그인 페이지로 리다이렉트
- localStorage의 토큰 삭제

### 5.2 보안
- JWT 토큰에는 GitHub Access Token이 포함되어 있으므로 **절대 노출하면 안 됨**
- localStorage 대신 httpOnly 쿠키 사용도 고려 (XSS 공격 방지)
- HTTPS 사용 필수

### 5.3 로그아웃
```javascript
function logout() {
  localStorage.removeItem('jwt_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('avatar_url');
  window.location.href = '/login';
}
```

---

## 6. 환경 변수 설정

프론트엔드 `.env` 파일:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
```

사용:
```javascript
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL
});
```

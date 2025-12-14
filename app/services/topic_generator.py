"""
학습 주제 생성 서비스
커밋 코드 분석을 통해 학습 가능한 CS 주제 생성
"""

from typing import List, Dict, Any
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import LearningTopicResponse, TopicExtractionResponse
from app.schemas.analysis import CommitDetailResponse

logger = logging.getLogger(__name__)


class TopicGenerator:
    """커밋에서 학습 주제를 생성하는 서비스"""

    def __init__(self):
        self.gemini_service = get_gemini_service()
        self._max_patch_preview_length = 1200

    def _build_topic_prompt(
        self,
        commits: List[CommitDetailResponse]
    ) -> str:
        """주제 생성용 프롬프트 구성"""

        # 커밋 정보 요약
        commits_summary = []
        for commit in commits:
            commit_info = f"""
커밋 SHA: {commit.sha[:7]}
메시지: {commit.message}
작성자: {commit.author}
변경 통계: +{commit.additions} -{commit.deletions} ({commit.filesChanged}개 파일)

변경된 파일:"""
            for file in commit.files[:5]:
                commit_info += f"\n파일: {file.filename} ({file.status})"
                commit_info += f"\n  +{file.additions} -{file.deletions}"
                if file.patch:
                    patch_preview = file.patch[:self._max_patch_preview_length]
                    if len(file.patch) > self._max_patch_preview_length:
                        patch_preview += "\n... (중략) ..."
                    commit_info += f"\n  Diff:\n{patch_preview}"

            commits_summary.append(commit_info)

        commits_text = "\n\n---\n\n".join(commits_summary)

        # 예시 출력 (모든 내용을 한국어로)
        example_output = """{
  "topics": [
    {
      "id": "topic_1",
      "title": "비동기 프로그래밍",
      "description": "Promise 기반 비동기 처리와 이벤트 루프의 동작 원리를 이해하고, async/await 패턴의 장점을 학습합니다.",
      "keywords": ["비동기", "프로미스", "이벤트 루프", "논블로킹", "동시성"]
    },
    {
      "id": "topic_2",
      "title": "REST API 설계 원칙",
      "description": "HTTP 메서드와 상태 코드의 올바른 사용법, 리소스 중심 설계 패턴을 학습합니다.",
      "keywords": ["REST", "API 설계", "HTTP", "상태 코드", "리소스"]
    },
    {
      "id": "topic_3",
      "title": "데이터베이스 인덱싱과 쿼리 최적화",
      "description": "인덱스의 내부 구조(B-Tree)와 쿼리 실행 계획을 분석하여 성능을 개선하는 방법을 학습합니다.",
      "keywords": ["인덱스", "쿼리 최적화", "실행 계획", "성능", "데이터베이스"]
    }
  ]
}"""

        prompt = f"""당신은 CS 교육 전문가입니다. 아래 커밋의 코드 변경사항을 분석하여 **학습할 수 있는 CS 주제**를 생성하세요.

**중요: 모든 주제와 설명은 반드시 한국어로 작성하세요.**

# 커밋 정보
{commits_text}

# 주제 생성 원칙
1. **실제 코드에서 발견된 기술/패턴**을 기반으로 주제를 생성하세요
2. **이론과 실무가 연결되는 주제**를 우선시하세요
3. **너무 지엽적인 주제는 제외**하고 보편적인 CS 개념을 선택하세요
4. **다양한 주제**를 3-5개 생성하세요

## 좋은 주제 예시
✅ "비동기 프로그래밍" - async/await 코드 발견 시
✅ "JWT 인증 시스템" - 토큰 기반 인증 구현 발견 시
✅ "해시 테이블과 시간복잡도" - Map/Dictionary 사용 발견 시
✅ "함수형 프로그래밍 패턴" - map/filter/reduce 체이닝 발견 시

## 나쁜 주제 예시 (금지)
❌ "변수명 짓기" - 너무 지엽적
❌ "세미콜론 사용법" - 실질적 학습 가치 낮음
❌ "코드 포맷팅" - CS 이론과 무관

# 주제 구조
각 주제는 다음을 포함해야 합니다:
- **id**: 고유 식별자 (topic_1, topic_2, ...)
- **title**: 주제 제목 (간결하고 명확하게, 한국어)
- **description**: 주제 설명 (학습할 내용을 2-3문장으로 서술, 한국어)
- **keywords**: 관련 키워드 (3-6개, 한국어)

# JSON 형식 예시
{example_output}

# 절대 규칙
1. **모든 내용을 한국어로 작성** (title, description, keywords 모두 한국어)
2. 유효한 JSON만 출력 (마크다운 금지)
3. 실제 커밋 코드에서 발견한 기술만 주제로 선택
4. 3-5개의 주제를 생성 (너무 많지 않게)
5. 각 주제는 CS 이론과 연결되어야 함
6. 문자열 이스케이프: \\n, \\"

위 커밋에서 학습 가능한 CS 주제를 **한국어로** JSON 형식으로 생성하세요:"""

        return prompt

    async def generate_topics(
        self,
        commits: List[CommitDetailResponse]
    ) -> TopicExtractionResponse:
        """
        커밋에서 학습 주제 생성

        Args:
            commits: 커밋 상세 정보 목록

        Returns:
            TopicExtractionResponse: 생성된 주제 목록
        """
        try:
            logger.info(f"[TopicGenerator] 주제 생성 시작: {len(commits)}개 커밋")

            # 프롬프트 구성
            prompt = self._build_topic_prompt(commits)
            logger.info(f"[TopicGenerator] 프롬프트 길이: {len(prompt)} 문자")

            # Gemini API 호출
            logger.info(f"[TopicGenerator] Gemini API 호출 중...")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.5,  # 창의성을 위해 약간 높은 온도
                max_tokens=4000
            )

            logger.info(f"[TopicGenerator] Gemini 응답 키: {list(response_data.keys())}")

            # 응답 검증
            if "topics" not in response_data:
                raise ValueError("응답에 'topics' 필드가 없습니다.")

            # 주제 파싱
            topics_data = response_data["topics"]
            topics = []

            for idx, topic_data in enumerate(topics_data):
                try:
                    if "id" not in topic_data:
                        topic_data["id"] = f"topic_{idx + 1}"

                    topic = LearningTopicResponse(**topic_data)
                    topics.append(topic)
                except Exception as e:
                    logger.warning(f"주제 {idx + 1} 파싱 실패: {str(e)}")
                    continue

            logger.info(f"[TopicGenerator] 주제 생성 완료: {len(topics)}개")

            return TopicExtractionResponse(
                topics=topics,
                metadata={
                    "totalCommits": len(commits),
                    "extractedCount": len(topics),
                    "extractedAt": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"[TopicGenerator] 주제 생성 실패: {str(e)}")
            raise ValueError(f"주제 생성 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_topic_generator = None


def get_topic_generator() -> TopicGenerator:
    """TopicGenerator 싱글톤 인스턴스 반환"""
    global _topic_generator
    if _topic_generator is None:
        _topic_generator = TopicGenerator()
    return _topic_generator

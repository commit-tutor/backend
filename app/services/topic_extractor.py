"""
학습 주제 추출 서비스
커밋 코드 분석을 통해 학습 가능한 CS 주제 추출
"""

from typing import List, Dict, Any
import logging
from datetime import datetime

from app.services.gemini_service import get_gemini_service
from app.schemas.quiz import LearningTopicResponse, TopicExtractionResponse
from app.schemas.analysis import CommitDetailResponse

logger = logging.getLogger(__name__)


class TopicExtractorService:
    """커밋에서 학습 주제를 추출하는 서비스"""

    def __init__(self):
        self.gemini_service = get_gemini_service()
        self._max_patch_preview_length = 1200

    def _build_topic_extraction_prompt(
        self,
        commits: List[CommitDetailResponse]
    ) -> str:
        """주제 추출용 프롬프트 생성"""

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

        # 예시 출력
        example_output = """{
  "topics": [
    {
      "id": "topic_1",
      "title": "비동기 프로그래밍 (Async/Await)",
      "description": "Promise 기반 비동기 처리와 이벤트 루프의 동작 원리를 이해하고, async/await 패턴의 장점을 학습합니다.",
      "difficulty": "medium",
      "keywords": ["async", "await", "Promise", "비동기", "event loop", "non-blocking"]
    },
    {
      "id": "topic_2",
      "title": "RESTful API 설계 원칙",
      "description": "HTTP 메서드와 상태 코드의 올바른 사용법, 리소스 중심 설계 패턴을 학습합니다.",
      "difficulty": "easy",
      "keywords": ["REST", "HTTP", "API", "CRUD", "stateless"]
    },
    {
      "id": "topic_3",
      "title": "데이터베이스 인덱싱과 쿼리 최적화",
      "description": "인덱스의 내부 구조(B-Tree)와 쿼리 실행 계획을 분석하여 성능을 개선하는 방법을 학습합니다.",
      "difficulty": "hard",
      "keywords": ["인덱스", "B-Tree", "쿼리 최적화", "실행 계획", "성능"]
    }
  ]
}"""

        prompt = f"""당신은 CS 교육 전문가입니다. 아래 커밋의 코드 변경사항을 분석하여 **학습할 수 있는 CS 주제**를 추출하세요.

# 커밋 정보
{commits_text}

# 주제 추출 원칙
1. **실제 코드에서 발견된 기술/패턴**을 기반으로 주제를 추출하세요
2. **이론과 실무가 연결되는 주제**를 우선시하세요
3. **너무 지엽적인 주제는 제외**하고 보편적인 CS 개념을 선택하세요
4. **난이도가 다양**하도록 3-5개 주제를 추출하세요

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
- **title**: 주제 제목 (간결하고 명확하게)
- **description**: 주제 설명 (학습할 내용을 2-3문장으로 서술)
- **difficulty**: 난이도 (easy, medium, hard)
  - easy: 기본 개념과 문법
  - medium: 설계 패턴, 알고리즘, 데이터 구조
  - hard: 성능 최적화, 시스템 설계, 고급 알고리즘
- **keywords**: 관련 키워드 (3-6개)

# JSON 형식 예시
{example_output}

# 절대 규칙
1. 유효한 JSON만 출력 (마크다운 금지)
2. 실제 커밋 코드에서 발견한 기술만 주제로 선택
3. 3-5개의 주제를 추출 (너무 많지 않게)
4. 각 주제는 CS 이론과 연결되어야 함
5. 난이도가 다양하도록 구성
6. 문자열 이스케이프: \\n, \\"

위 커밋에서 학습 가능한 CS 주제를 JSON으로 추출하세요:"""

        return prompt

    async def extract_topics(
        self,
        commits: List[CommitDetailResponse]
    ) -> TopicExtractionResponse:
        """
        커밋에서 학습 주제 추출

        Args:
            commits: 커밋 상세 정보 목록

        Returns:
            TopicExtractionResponse: 추출된 주제 목록
        """
        try:
            logger.info(f"[TopicExtractor] 주제 추출 시작: {len(commits)}개 커밋")

            # 프롬프트 구성
            prompt = self._build_topic_extraction_prompt(commits)
            logger.info(f"[TopicExtractor] 프롬프트 길이: {len(prompt)} 문자")

            # Gemini API 호출
            logger.info(f"[TopicExtractor] Gemini API 호출 중...")
            response_data = await self.gemini_service.generate_json(
                prompt=prompt,
                temperature=0.5,  # 창의성을 위해 약간 높은 온도
                max_tokens=4000
            )

            logger.info(f"[TopicExtractor] Gemini 응답 키: {list(response_data.keys())}")

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

            logger.info(f"[TopicExtractor] 주제 추출 완료: {len(topics)}개")

            return TopicExtractionResponse(
                topics=topics,
                metadata={
                    "totalCommits": len(commits),
                    "extractedCount": len(topics),
                    "extractedAt": datetime.utcnow().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"[TopicExtractor] 주제 추출 실패: {str(e)}")
            raise ValueError(f"주제 추출 중 오류 발생: {str(e)}")


# 싱글톤 인스턴스
_topic_extractor_service = None


def get_topic_extractor_service() -> TopicExtractorService:
    """TopicExtractorService 싱글톤 인스턴스 반환"""
    global _topic_extractor_service
    if _topic_extractor_service is None:
        _topic_extractor_service = TopicExtractorService()
    return _topic_extractor_service

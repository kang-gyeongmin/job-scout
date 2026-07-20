"""채점 결과 누적 저장소 — 대시보드·Notion 연동의 데이터 원본.

data/history.json에 실행일(date)이 붙은 채점 결과를 계속 쌓는다.
seen.json(재알림 방지용 id 집합)과 달리 점수·요약까지 보존하므로
과거 공고를 대시보드에서 다시 볼 수 있다.

중복 제거는 두 겹이다:
- id 기준 — 같은 공고가 재채점돼도(예: 발송 실패 후 재실행) 다시 쌓이지 않음
- 정규화한 (회사, 제목) 기준 — 같은 공고가 다른 사이트에 올라오거나
  재게시로 id가 바뀌어도 걸러냄
"""
import json
import re
from dataclasses import asdict
from pathlib import Path

from src.agent import ScoredJob
from src.models import JobPosting


def _dedup_key(company: str, title: str) -> str:
    """회사+제목을 비교용으로 정규화 — 공백·대소문자·괄호류 차이를 무시한다."""
    return re.sub(r"[\s\[\]()〔〕【】·,]+", "", f"{company}|{title}").casefold()


class HistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[dict] = []
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, scored: list[ScoredJob], date: str,
            postings_by_id: dict[str, JobPosting] | None = None) -> list[dict]:
        """새 채점 결과를 추가하고, 실제로 새로 추가된 항목만 반환한다.

        postings_by_id가 있으면 원본 공고의 모집 시작일·마감일을 붙인다
        (LLM 출력에는 없는 메타데이터).
        """
        known_ids = {e["id"] for e in self.entries}
        known_keys = {_dedup_key(e["company"], e["title"]) for e in self.entries}
        added = []
        for job in scored:
            key = _dedup_key(job.company, job.title)
            if job.id in known_ids or key in known_keys:
                continue
            known_ids.add(job.id)
            known_keys.add(key)
            posting = (postings_by_id or {}).get(job.id)
            added.append({**asdict(job), "date": date,
                          "start_date": posting.posted_at if posting else "",
                          "deadline": posting.deadline if posting else ""})
        if added:
            self.entries.extend(added)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.entries, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        return added

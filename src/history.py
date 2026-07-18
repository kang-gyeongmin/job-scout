"""채점 결과 누적 저장소 — 대시보드·Notion 연동의 데이터 원본.

data/history.json에 실행일(date)이 붙은 채점 결과를 계속 쌓는다.
seen.json(재알림 방지용 id 집합)과 달리 점수·요약까지 보존하므로
과거 공고를 대시보드에서 다시 볼 수 있다. id 기준으로 중복을 막는다.
"""
import json
from dataclasses import asdict
from pathlib import Path

from src.agent import ScoredJob


class HistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[dict] = []
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, scored: list[ScoredJob], date: str) -> list[dict]:
        """새 채점 결과를 추가하고, 실제로 새로 추가된 항목만 반환한다.

        이메일 발송 실패로 같은 공고가 다음 실행에서 다시 채점돼도
        중복으로 쌓이지 않는다 (Notion 연동도 반환값만 올리므로 안전).
        """
        known = {e["id"] for e in self.entries}
        added = [{**asdict(job), "date": date}
                 for job in scored if job.id not in known]
        if added:
            self.entries.extend(added)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.entries, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        return added

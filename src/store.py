import json
from pathlib import Path

from src.models import JobPosting


class SeenStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._ids: set[str] = set()
        if self.path.exists():
            self._ids = set(json.loads(self.path.read_text(encoding="utf-8")))

    def filter_new(self, postings: list[JobPosting]) -> list[JobPosting]:
        return [p for p in postings if p.id not in self._ids]

    def mark(self, ids: list[str]) -> None:
        self._ids.update(ids)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(self._ids), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

from src.agent import ScoredJob
from src.history import HistoryStore


def _job(job_id: str, score: int = 7) -> ScoredJob:
    return ScoredJob(id=job_id, site="wanted", title="제목", company="회사",
                     url=f"https://example.com/{job_id}", score=score,
                     reason="이유", summary="요약")


def test_add_appends_and_persists(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(path)
    added = store.add([_job("wanted:1"), _job("wanted:2")], "2026-07-17")
    assert len(added) == 2
    assert added[0]["date"] == "2026-07-17"

    reloaded = HistoryStore(path)
    assert len(reloaded.entries) == 2
    assert reloaded.entries[0]["id"] == "wanted:1"


def test_add_skips_duplicate_ids(tmp_path):
    path = tmp_path / "history.json"
    HistoryStore(path).add([_job("wanted:1")], "2026-07-16")
    added = HistoryStore(path).add([_job("wanted:1"), _job("wanted:3")], "2026-07-17")
    assert [e["id"] for e in added] == ["wanted:3"]
    assert len(HistoryStore(path).entries) == 2


def test_add_nothing_does_not_create_file(tmp_path):
    path = tmp_path / "history.json"
    assert HistoryStore(path).add([], "2026-07-17") == []
    assert not path.exists()

from pathlib import Path
from src.models import JobPosting
from src.store import SeenStore


def make_posting(pid: str) -> JobPosting:
    return JobPosting(
        id=pid, site="wanted", title="데이터 엔지니어", company="회사",
        location="서울", experience="신입", url=f"https://x/{pid}",
        description="", posted_at="",
    )


def test_filter_new_excludes_marked_ids(tmp_path: Path):
    store = SeenStore(tmp_path / "data" / "seen.json")
    a, b = make_posting("wanted:1"), make_posting("wanted:2")
    store.mark(["wanted:1"])
    assert store.filter_new([a, b]) == [b]


def test_mark_persists_across_instances(tmp_path: Path):
    path = tmp_path / "seen.json"
    SeenStore(path).mark(["wanted:1"])
    assert SeenStore(path).filter_new([make_posting("wanted:1")]) == []

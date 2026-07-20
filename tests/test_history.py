from src.agent import ScoredJob
from src.history import HistoryStore
from src.models import JobPosting


def _job(job_id: str, score: int = 7, title: str = "제목",
         company: str = "회사") -> ScoredJob:
    return ScoredJob(id=job_id, site="wanted", title=title, company=company,
                     url=f"https://example.com/{job_id}", score=score,
                     reason="이유", summary="요약")


def test_add_appends_and_persists(tmp_path):
    path = tmp_path / "history.json"
    store = HistoryStore(path)
    added = store.add([_job("wanted:1"), _job("wanted:2", title="제목2")],
                      "2026-07-17")
    assert len(added) == 2
    assert added[0]["date"] == "2026-07-17"

    reloaded = HistoryStore(path)
    assert len(reloaded.entries) == 2
    assert reloaded.entries[0]["id"] == "wanted:1"


def test_add_skips_duplicate_ids(tmp_path):
    path = tmp_path / "history.json"
    HistoryStore(path).add([_job("wanted:1")], "2026-07-16")
    added = HistoryStore(path).add(
        [_job("wanted:1"), _job("wanted:3", title="다른 제목")], "2026-07-17")
    assert [e["id"] for e in added] == ["wanted:3"]
    assert len(HistoryStore(path).entries) == 2


def test_add_skips_same_company_title_across_sites(tmp_path):
    """같은 공고가 다른 사이트/재게시로 id만 바뀌어 들어와도 걸러진다."""
    path = tmp_path / "history.json"
    HistoryStore(path).add(
        [_job("wanted:1", title="[신입] 데이터 엔지니어", company="A사")],
        "2026-07-16")
    added = HistoryStore(path).add(
        [_job("saramin:9", title="(신입) 데이터엔지니어", company="A 사")],
        "2026-07-17")
    assert added == []


def test_add_attaches_recruit_dates_from_postings(tmp_path):
    posting = JobPosting(id="wanted:1", site="wanted", title="제목",
                         company="회사", location="서울", experience="신입",
                         url="https://example.com/1", description="",
                         posted_at="2026-07-10", deadline="2026-07-18")
    added = HistoryStore(tmp_path / "h.json").add(
        [_job("wanted:1")], "2026-07-17", {"wanted:1": posting})
    assert added[0]["start_date"] == "2026-07-10"
    assert added[0]["deadline"] == "2026-07-18"


def test_add_nothing_does_not_create_file(tmp_path):
    path = tmp_path / "history.json"
    assert HistoryStore(path).add([], "2026-07-17") == []
    assert not path.exists()

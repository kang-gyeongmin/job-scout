import json
from pathlib import Path

from src.agent import build_search_tool, extract_json
from src.models import JobPosting
from src.store import SeenStore


def fake_search(keyword: str, limit: int = 20) -> list[JobPosting]:
    return [JobPosting(id="wanted:1", site="wanted", title=f"{keyword} 주니어",
                       company="A사", location="서울", experience="신입",
                       url="https://x/1", description="파이프라인 구축", posted_at="")]


async def test_search_tool_filters_seen_and_records_ids(tmp_path: Path):
    store = SeenStore(tmp_path / "seen.json")
    fetched_ids: list[str] = []
    handler = build_search_tool({"wanted": fake_search}, store, fetched_ids, [])

    result = await handler({"site": "wanted", "keyword": "데이터 엔지니어"})
    postings = json.loads(result["content"][0]["text"])
    assert postings[0]["id"] == "wanted:1"
    assert fetched_ids == ["wanted:1"]

    store.mark(["wanted:1"])
    result = await handler({"site": "wanted", "keyword": "데이터 엔지니어"})
    assert json.loads(result["content"][0]["text"]) == []


async def test_search_tool_unknown_site_returns_error_text(tmp_path: Path):
    handler = build_search_tool({}, SeenStore(tmp_path / "s.json"), [], [])
    result = await handler({"site": "wanted", "keyword": "x"})
    assert "사용할 수 없는 사이트" in result["content"][0]["text"]


async def test_search_tool_collector_error_recorded_as_failure(tmp_path: Path):
    def broken_search(keyword: str, limit: int = 20):
        raise RuntimeError("connection refused")

    failures: list[str] = []
    handler = build_search_tool({"wanted": broken_search},
                                SeenStore(tmp_path / "s.json"), [], failures)
    result = await handler({"site": "wanted", "keyword": "x"})
    assert "수집 실패" in result["content"][0]["text"]
    assert failures and "wanted" in failures[0]


def test_extract_json_strips_code_fence():
    text = '채점 결과입니다.\n```json\n[{"id": "wanted:1", "score": 8}]\n```'
    assert extract_json(text) == [{"id": "wanted:1", "score": 8}]

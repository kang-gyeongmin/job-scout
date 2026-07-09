import json
from pathlib import Path

import pytest

from src.agent import ScoredJob, build_search_tool, extract_json, parse_scored
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


async def test_search_tool_dedups_within_same_run(tmp_path: Path):
    """같은 실행 안에서 다른 키워드로 재검색해도 이미 가져온 공고는 제외된다.
    (store에는 기록하지 않음 — seen과는 별개의 실행 내 중복 제거)"""
    store = SeenStore(tmp_path / "seen.json")
    fetched_ids: list[str] = []
    handler = build_search_tool({"wanted": fake_search}, store, fetched_ids, [])

    result = await handler({"site": "wanted", "keyword": "데이터"})
    postings = json.loads(result["content"][0]["text"])
    assert postings[0]["id"] == "wanted:1"
    assert fetched_ids == ["wanted:1"]

    # 같은 posting을 반환하는 다른 키워드 검색 — store는 마킹되지 않았지만
    # 이번 실행에서 이미 가져왔으므로 빈 payload여야 한다.
    result = await handler({"site": "wanted", "keyword": "엔지니어"})
    assert json.loads(result["content"][0]["text"]) == []
    assert fetched_ids == ["wanted:1"]


def test_extract_json_no_brackets_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("아무 결과도 없습니다.")


def test_parse_scored_empty_text_returns_empty_list():
    assert parse_scored("") == []
    assert parse_scored("   ") == []


def test_parse_scored_coerces_string_score_to_int():
    text = ('```json\n[{"id": "wanted:1", "site": "wanted", "title": "t", '
            '"company": "c", "url": "https://x/1", "score": "8", '
            '"reason": "r", "summary": "s"}]\n```')
    scored = parse_scored(text)
    assert scored == [ScoredJob(id="wanted:1", site="wanted", title="t",
                                company="c", url="https://x/1", score=8,
                                reason="r", summary="s")]
    assert isinstance(scored[0].score, int)


def test_parse_scored_invalid_json_raises_runtime_error():
    with pytest.raises(RuntimeError, match="에이전트 응답 파싱 실패"):
        parse_scored("이 응답에는 JSON 배열이 없습니다.")


def test_parse_scored_missing_field_raises_runtime_error():
    text = '```json\n[{"id": "wanted:1", "score": 8}]\n```'
    with pytest.raises(RuntimeError, match="에이전트 응답 파싱 실패"):
        parse_scored(text)

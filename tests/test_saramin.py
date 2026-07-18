import json
from pathlib import Path

import pytest

from src.collectors.saramin import parse_list, search

FIXTURE = json.loads(
    Path("tests/fixtures/saramin_list.json").read_text(encoding="utf-8")
)


def test_parse_list_returns_postings():
    postings = parse_list(FIXTURE)
    assert len(postings) == 2
    p = postings[0]
    assert p.site == "saramin"
    assert p.id == "saramin:50000001"
    assert p.title == "데이터 엔지니어 신입/주니어 채용"
    assert p.company == "(주)데이터컴퍼니"
    assert p.url.startswith("http://www.saramin.co.kr/")
    assert p.experience == "신입"
    assert p.posted_at == "2026-07-16"


def test_parse_list_unescapes_html_entities():
    p = parse_list(FIXTURE)[0]
    assert p.location == "서울 > 강남구"  # 원문은 "서울 &gt; 강남구"


def test_parse_list_builds_description_from_keywords():
    p = parse_list(FIXTURE)[0]
    assert "Python,Spark,Airflow" in p.description
    assert "정규직" in p.description


def test_parse_list_empty_response():
    assert parse_list({"jobs": {"job": []}}) == []
    assert parse_list({}) == []


def test_search_without_api_key_raises(monkeypatch):
    monkeypatch.delenv("SARAMIN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SARAMIN_API_KEY"):
        search("데이터 엔지니어")

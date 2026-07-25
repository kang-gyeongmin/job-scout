import json
from pathlib import Path

from src.collectors.catch import parse_detail, parse_list

LIST = json.loads(Path("tests/fixtures/catch_list.json").read_text(encoding="utf-8"))
DETAIL_HTML = Path("tests/fixtures/catch_detail.html").read_text(encoding="utf-8")


def test_parse_list_returns_postings():
    postings = parse_list(LIST)
    assert len(postings) > 0
    p = postings[0]
    assert p.site == "catch"
    assert p.id.startswith("catch:")
    assert p.title
    assert p.company
    assert p.url.startswith("https://www.catch.co.kr/NCS/RecruitInfoDetails/")


def test_parse_list_deadline_from_apply_end():
    # ApplyEndDatetime "2026-08-14T..." -> "2026-08-14"
    p = parse_list(LIST)[0]
    assert len(p.deadline) == 10 and p.deadline.startswith("2026-")


def test_parse_list_company_size_empty_before_detail():
    # 목록 JSON엔 기업규모가 없다 — 상세 조회로 채운다
    assert parse_list(LIST)[0].company_size == ""


def test_parse_list_description_has_job_depth():
    p = parse_list(LIST)[0]
    assert p.description  # Depth(직무) 등이 담긴다


def test_parse_detail_extracts_company_size():
    items = parse_detail(DETAIL_HTML)
    assert items.get("기업규모") == "중견기업"


def test_parse_detail_has_industry_and_revenue():
    items = parse_detail(DETAIL_HTML)
    assert "업종" in items and "매출" in items

from pathlib import Path

from src.collectors.work24 import LIST_URL, _fix_year, parse_list

FIXTURE = Path("tests/fixtures/work24_list.html").read_text(encoding="utf-8")


def test_parse_list_returns_postings():
    postings = parse_list(FIXTURE)
    assert len(postings) == 2  # 기업탐방형(C) 카드는 제외
    p = postings[0]
    assert p.site == "work24"
    assert p.id == "work24:PG0020425202607090002"
    assert p.title == "[(주)텐씨엘] 휴먼잡트러스트 IT 3기"
    assert p.company == "주식회사 텐씨엘"
    assert p.location == "서울"
    assert p.experience == "인턴형"
    assert p.url == LIST_URL


def test_parse_list_skips_company_visit_type():
    ids = [p.id for p in parse_list(FIXTURE)]
    assert "work24:PG9999999999999999999" not in ids


def test_parse_list_description_has_recruit_period():
    p = parse_list(FIXTURE)[0]
    assert "모집기간" in p.description
    assert "운영기관" in p.description


def test_posted_at_converts_two_digit_year():
    p = parse_list(FIXTURE)[0]
    assert p.posted_at == "2026-07-10"


def test_fix_year_invalid_returns_empty():
    assert _fix_year("") == ""
    assert _fix_year("2026-07-10") == ""  # 이미 4자리 연도면 목록 형식이 아님

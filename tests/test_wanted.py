import json
from pathlib import Path

from src.collectors.wanted import parse_list

FIXTURE = json.loads(
    Path("tests/fixtures/wanted_list.json").read_text(encoding="utf-8")
)


def test_parse_list_returns_postings():
    postings = parse_list(FIXTURE)
    assert len(postings) > 0
    p = postings[0]
    assert p.site == "wanted"
    assert p.id.startswith("wanted:")
    assert p.title
    assert p.company
    assert p.url.startswith("https://www.wanted.co.kr/wd/")


def _item(annual_from, annual_to):
    """experience 포맷 테스트용 최소 목록 항목."""
    return {
        "id": 1,
        "position": "제목",
        "company": {"name": "회사"},
        "address": {"location": "서울"},
        "annual_from": annual_from,
        "annual_to": annual_to,
    }


def test_experience_entry_level_shows_sinip():
    p = parse_list({"data": [_item(0, 2)]})[0]
    assert p.experience == "신입~2년"


def test_experience_to_100_is_mugwan_sentinel():
    p = parse_list({"data": [_item(3, 100)]})[0]
    assert p.experience == "3년~무관"


def test_experience_nonzero_from_uses_year_prefix():
    p = parse_list({"data": [_item(1, 3)]})[0]
    assert p.experience == "1년~3년"


def test_experience_missing_fields_is_empty():
    item = _item(0, 2)
    del item["annual_from"], item["annual_to"]
    p = parse_list({"data": [item]})[0]
    assert p.experience == ""

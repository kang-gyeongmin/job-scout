import json
from pathlib import Path

from src.collectors.zighang import _format_experience, parse_list

LIST = json.loads(Path("tests/fixtures/zighang_list.json").read_text(encoding="utf-8"))


def test_parse_list_returns_postings():
    postings = parse_list(LIST)
    assert len(postings) > 0
    p = postings[0]
    assert p.site == "zighang"
    assert p.id.startswith("zighang:")
    assert p.title
    assert p.company
    assert p.url.startswith("https://zighang.com/recruitment/")


def test_parse_list_location_and_deadline():
    p = parse_list(LIST)[0]
    assert p.location  # regions
    # endDate가 있으면 ISO 날짜 앞 10자, 없으면 ""
    assert p.deadline == "" or len(p.deadline) == 10


def test_format_experience_newcomer():
    assert _format_experience(0, 0) == "신입"
    assert _format_experience(0, 3) == "신입~3년"
    assert _format_experience(2, 5) == "2년~5년"
    assert _format_experience(0, 100) == "신입~무관"
    assert _format_experience(None, None) == ""

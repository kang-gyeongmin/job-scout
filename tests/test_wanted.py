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

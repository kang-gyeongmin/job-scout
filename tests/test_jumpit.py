import json
from pathlib import Path

from src.collectors.jumpit import parse_list

FIXTURE = json.loads(
    Path("tests/fixtures/jumpit_list.json").read_text(encoding="utf-8")
)


def _item(min_career, max_career, newcomer=False, locations=None, **extra):
    """parse_list 테스트용 최소 항목."""
    return {
        "id": 1,
        "title": "데이터 엔지니어",
        "companyName": "회사",
        "minCareer": min_career,
        "maxCareer": max_career,
        "newcomer": newcomer,
        "locations": ["서울 강남구"] if locations is None else locations,
        **extra,
    }


def _parse(items, **kw):
    return parse_list({"result": {"positions": items}}, **kw)


def test_parse_list_returns_postings():
    postings = parse_list(FIXTURE)
    assert len(postings) > 0
    p = postings[0]
    assert p.site == "jumpit"
    assert p.id.startswith("jumpit:")
    assert p.title
    assert p.company
    assert p.url.startswith("https://jumpit.saramin.co.kr/position/")


def test_max_experience_from_drops_over_experience():
    # 최소 경력 5년은 max_experience_from=1이면 제외
    assert _parse([_item(5, 8)], max_experience_from=1) == []


def test_max_experience_from_keeps_entry_and_junior():
    kept = _parse([_item(0, 0, newcomer=True), _item(1, 3)],
                  max_experience_from=1)
    assert len(kept) == 2


def test_newcomer_experience_label():
    p = _parse([_item(0, 0, newcomer=True)])[0]
    assert p.experience == "신입"


def test_junior_experience_label():
    p = _parse([_item(1, 3)])[0]
    assert p.experience == "1년~3년"


def test_non_capital_location_dropped():
    assert _parse([_item(0, 0, newcomer=True, locations=["부산 해운대구"])]) == []


def test_empty_location_kept():
    # 재택·전국 등 지역 미표기 공고는 남긴다
    assert len(_parse([_item(0, 0, newcomer=True, locations=[])])) == 1


def test_always_open_has_no_deadline():
    p = _parse([_item(0, 0, newcomer=True, alwaysOpen=True,
                      closedAt="2026-08-18T23:59:59")])[0]
    assert p.deadline == ""


def test_closed_at_becomes_deadline():
    p = _parse([_item(0, 0, newcomer=True, alwaysOpen=False,
                      closedAt="2026-08-18T23:59:59")])[0]
    assert p.deadline == "2026-08-18"

from pathlib import Path

from src.collectors.jobkorea import (
    _is_sinip,
    _to_iso,
    parse_detail,
    parse_search_ids,
)

SEARCH = Path("tests/fixtures/jobkorea_search.html").read_text(encoding="utf-8")
DETAIL = Path("tests/fixtures/jobkorea_detail.html").read_text(encoding="utf-8")


def test_parse_search_ids_dedups_and_orders():
    ids = parse_search_ids(SEARCH)
    assert len(ids) > 0
    assert len(ids) == len(set(ids))  # 중복 없음
    assert all(i.isdigit() for i in ids)


def test_parse_detail_core_fields():
    p = parse_detail(DETAIL, "49819763")
    assert p.site == "jobkorea"
    assert p.id == "jobkorea:49819763"
    assert p.company == "아이시"
    assert "소프트웨어 개발자" in p.title
    assert p.url.endswith("/Recruit/GI_Read/49819763")


def test_parse_detail_experience_and_deadline():
    p = parse_detail(DETAIL, "49819763")
    assert "신입" in p.experience
    assert p.deadline == "2026-10-19"


def test_parse_detail_company_size():
    p = parse_detail(DETAIL, "49819763")
    assert p.company_size == "중소기업"


def test_to_iso_formats():
    assert _to_iso("2026.10.19(월) 채용 시 마감") == "2026-10-19"
    assert _to_iso("2026.1.5") == "2026-01-05"
    assert _to_iso("상시채용") == ""


def test_is_sinip():
    assert _is_sinip("신입") is True
    assert _is_sinip("신입·경력") is True
    assert _is_sinip("경력무관") is True
    assert _is_sinip("경력 3년") is False

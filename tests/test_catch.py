from pathlib import Path

from src.collectors.catch import _deadline_from_title, parse_detail

FIXTURE = Path("tests/fixtures/catch_detail.html").read_text(encoding="utf-8")


def test_parse_detail_extracts_core_fields():
    p = parse_detail(FIXTURE, "561488")
    assert p.site == "catch"
    assert p.id == "catch:561488"
    assert p.company == "메디톡스"
    assert "채용" in p.title
    assert p.url == "https://www.catch.co.kr/NCS/RecruitInfoDetails/561488"


def test_parse_detail_extracts_company_size():
    p = parse_detail(FIXTURE, "561488")
    assert p.company_size == "중견기업"


def test_parse_detail_description_has_industry_and_size():
    p = parse_detail(FIXTURE, "561488")
    assert "기업규모: 중견기업" in p.description
    assert "업종:" in p.description


def test_parse_detail_experience_from_title():
    p = parse_detail(FIXTURE, "561488")
    assert p.experience in ("신입", "경력")  # 제목에 '신입/경력'


def test_deadline_from_title_parses_mmdd():
    # 미래 날짜는 올해로
    assert _deadline_from_title("[X] 공고 (~12/31)").endswith("-12-31")


def test_deadline_from_title_empty_when_absent():
    assert _deadline_from_title("마감 표기 없는 제목") == ""

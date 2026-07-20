from src.notion_sync import PROPERTIES, build_page

ENTRY = {
    "id": "saramin:50000001", "site": "saramin", "title": "데이터 엔지니어",
    "company": "회사", "url": "https://example.com/1",
    "score": 8, "reason": "스택 일치", "summary": "요" * 3000,
    "date": "2026-07-17", "start_date": "2026-07-10", "deadline": "2026-07-18",
}


def test_build_page_maps_all_schema_properties():
    page = build_page(ENTRY, "db-123")
    assert page["parent"] == {"database_id": "db-123"}
    assert set(page["properties"]) == set(PROPERTIES)


def test_build_page_values():
    props = build_page(ENTRY, "db-123")["properties"]
    assert props["제목"]["title"][0]["text"]["content"] == "데이터 엔지니어"
    assert props["사이트"]["select"]["name"] == "사람인"
    assert props["점수"]["number"] == 8
    assert props["상태"]["select"]["name"] == "신규"
    assert props["수집일"]["date"]["start"] == "2026-07-17"
    assert props["링크"]["url"] == "https://example.com/1"


def test_build_page_includes_recruit_dates():
    props = build_page(ENTRY, "db-123")["properties"]
    assert props["시작일"]["date"]["start"] == "2026-07-10"
    assert props["마감일"]["date"]["start"] == "2026-07-18"


def test_build_page_omits_empty_dates():
    entry = {**ENTRY, "start_date": "", "deadline": ""}
    props = build_page(entry, "db-123")["properties"]
    assert "시작일" not in props and "마감일" not in props  # 빈 date는 API 오류


def test_build_page_truncates_long_text_to_notion_limit():
    props = build_page(ENTRY, "db-123")["properties"]
    assert len(props["요약"]["rich_text"][0]["text"]["content"]) == 2000

from src.enrich import (
    FAIL_STATUS,
    MANUAL_SITE,
    _html_to_text,
    _manual_id,
    build_enrich_update,
    build_failure_update,
    build_query_filter,
    extract_pending,
)

SCORED = {"title": "데이터 엔지니어", "company": "회사", "score": 8,
          "reason": "스택 일치", "summary": "요약"}


def test_query_filter_targets_empty_score_with_link():
    f = build_query_filter()["and"]
    conds = {c["property"]: c for c in f}
    assert conds["점수"]["number"]["is_empty"] is True
    assert conds["링크"]["url"]["is_not_empty"] is True
    # 상태 옵션은 필터에서 참조하지 않는다(옵션 없을 때 400 방지)
    assert "상태" not in conds


def _page(page_id, url, title="", status=None):
    props = {"링크": {"url": url}}
    props["제목"] = {"title": [{"text": {"content": title}}] if title else []}
    props["상태"] = {"select": {"name": status} if status else None}
    return {"id": page_id, "properties": props}


def test_extract_pending_reads_url_and_title_state():
    resp = {"results": [_page("p1", "https://x.com/1"),
                        _page("p2", "https://x.com/2", title="이미 제목")]}
    pending = extract_pending(resp)
    assert [p["page_id"] for p in pending] == ["p1", "p2"]
    assert pending[0]["title_empty"] is True
    assert pending[1]["title_empty"] is False


def test_extract_pending_skips_rows_without_link():
    resp = {"results": [{"id": "p3", "properties": {"링크": {"url": None}}}]}
    assert extract_pending(resp) == []


def test_extract_pending_skips_failed_status():
    resp = {"results": [_page("p4", "https://x.com/4", status=FAIL_STATUS)]}
    assert extract_pending(resp) == []


def test_build_enrich_update_fills_score_reason_summary():
    props = build_enrich_update(SCORED, "https://x.com/1", "2026-07-20", True)
    assert props["점수"]["number"] == 8
    assert props["사이트"]["select"]["name"] == MANUAL_SITE
    assert props["이유"]["rich_text"][0]["text"]["content"] == "스택 일치"
    assert props["제목"]["title"][0]["text"]["content"] == "데이터 엔지니어"
    assert props["공고 ID"]["rich_text"][0]["text"]["content"].startswith("manual:")


def test_build_enrich_update_preserves_user_title():
    # 사용자가 제목을 이미 적었으면(title_empty=False) 제목을 건드리지 않는다
    props = build_enrich_update(SCORED, "https://x.com/1", "2026-07-20", False)
    assert "제목" not in props


def test_manual_id_is_stable_per_url():
    assert _manual_id("https://x.com/1") == _manual_id("https://x.com/1")
    assert _manual_id("https://x.com/1") != _manual_id("https://x.com/2")


def test_build_failure_update_sets_status():
    props = build_failure_update("타임아웃")
    assert props["상태"]["select"]["name"] == FAIL_STATUS
    assert "분석 실패" in props["이유"]["rich_text"][0]["text"]["content"]


def test_html_to_text_strips_scripts():
    html = "<html><body><script>var x=1</script><h1>제목</h1><p>본문</p></body></html>"
    text = _html_to_text(html)
    assert "제목" in text and "본문" in text
    assert "var x" not in text

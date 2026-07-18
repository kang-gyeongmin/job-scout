import json

from src.dashboard import render_dashboard

ENTRY = {
    "id": "wanted:1", "site": "wanted", "title": "데이터 엔지니어",
    "company": "회사<주>", "url": "https://example.com/1",
    "score": 8, "reason": "스택 일치", "summary": "요약", "date": "2026-07-17",
}


def test_render_contains_embedded_data():
    html_out = render_dashboard([ENTRY])
    assert "데이터 엔지니어" in html_out
    assert "job-scout 대시보드" in html_out
    # 데이터가 유효한 JSON으로 내장되는지 (이스케이프 복원 후) 확인
    start = html_out.index("const JOBS = ") + len("const JOBS = ")
    end = html_out.index(";\n", start)
    parsed = json.loads(html_out[start:end].replace("<\\/", "</"))
    assert parsed[0]["id"] == "wanted:1"


def test_render_escapes_closing_script_in_data():
    entry = {**ENTRY, "summary": "본문에 </script> 포함"}
    html_out = render_dashboard([entry])
    body = html_out[html_out.index("const JOBS"):]
    assert "</script> 포함" not in body  # <\/script> 로 이스케이프되어야 함


def test_render_empty_history():
    html_out = render_dashboard([])
    assert "const JOBS = []" in html_out

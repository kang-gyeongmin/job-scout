"""수동 입력 링크 보강 — 사용자가 노션에 URL만 붙여 만든 row를 채점해 채운다.

동작(트리거 B): 점수가 비어 있고 링크가 있는 노션 페이지를 찾아, 그 URL의
페이지 본문을 읽고 profile.md 대비로 채점한 뒤 제목·회사·점수·이유·요약을
되쓴다. 매일 실행(src.main)에 포함되며, --enrich-only로 단독 실행도 된다.

- 읽기/채점에 실패한 페이지는 상태를 "분석실패"로 표시한다. 조회 필터가
  이 상태를 제외하므로 같은 URL을 매일 재시도하지 않는다(무한 재시도 방지).
- 임의의 사이트가 대상이라 정적 HTML은 잘 읽히지만 JS 렌더링·WAF 차단
  페이지는 본문이 비어 실패할 수 있다. 그 경우 노션 페이지 본문에 공고
  내용을 직접 붙여넣고 상태를 비우면 다음 실행에서 다시 시도된다.
"""
import datetime
import hashlib
import re

import httpx
from bs4 import BeautifulSoup

from src.agent import score_text
from src.notion_sync import API, _headers, _text

FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "text/html,application/xhtml+xml",
}
FAIL_STATUS = "분석실패"
MANUAL_SITE = "수동"


def _html_to_text(html: str) -> str:
    """HTML에서 스크립트·네비게이션 등을 걷어내고 본문 텍스트만 뽑는다."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_page_text(url: str) -> str:
    """URL을 받아 본문 텍스트를 반환한다. HTTP 오류는 예외로 전파된다."""
    resp = httpx.get(url, headers=FETCH_HEADERS, timeout=20, follow_redirects=True)
    resp.raise_for_status()
    return _html_to_text(resp.text)


def _manual_id(url: str) -> str:
    """URL을 안정적인 공고 ID로. 같은 URL은 항상 같은 값(중복 판별용)."""
    return "manual:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def build_query_filter() -> dict:
    """보강 대상(점수 없음 + 링크 있음) 조회 필터.

    분석실패 제외는 extract_pending에서 파이썬으로 처리한다 — 필터에서 상태
    옵션을 참조하면 옵션이 아직 없을 때(첫 실패 전) Notion이 400을 낸다.
    """
    return {"and": [
        {"property": "점수", "number": {"is_empty": True}},
        {"property": "링크", "url": {"is_not_empty": True}},
    ]}


def extract_pending(query_response: dict) -> list[dict]:
    """DB 조회 응답에서 보강 대상 페이지들을 뽑는다.

    각 항목: {"page_id", "url", "title_empty"(제목이 비어 있으면 True)}.
    링크가 없거나 상태가 분석실패인 페이지는 건너뛴다(무한 재시도 방지).
    """
    pending = []
    for page in query_response.get("results", []):
        props = page.get("properties", {})
        url = (props.get("링크") or {}).get("url")
        if not url:
            continue
        status = ((props.get("상태") or {}).get("select") or {}).get("name")
        if status == FAIL_STATUS:
            continue
        title_list = (props.get("제목") or {}).get("title", [])
        pending.append({
            "page_id": page["id"],
            "url": url,
            "title_empty": len(title_list) == 0,
        })
    return pending


def build_enrich_update(scored: dict, url: str, today: str,
                        title_empty: bool) -> dict:
    """채점 결과를 노션 페이지 업데이트(properties)로 변환한다."""
    props = {
        "회사": _text(scored["company"]),
        "사이트": {"select": {"name": MANUAL_SITE}},
        "점수": {"number": scored["score"]},
        "수집일": {"date": {"start": today}},
        "이유": _text(scored["reason"]),
        "요약": _text(scored["summary"]),
        "공고 ID": _text(_manual_id(url)),
    }
    # 사용자가 제목을 안 적었을 때만 추출한 제목으로 채운다(직접 쓴 메모는 보존).
    if title_empty:
        props["제목"] = {"title": [{"text": {"content": scored["title"][:2000]}}]}
    return props


def build_failure_update(reason: str) -> dict:
    """읽기/채점 실패 시 상태를 분석실패로 표시하는 업데이트."""
    return {
        "상태": {"select": {"name": FAIL_STATUS}},
        "이유": _text(f"분석 실패: {reason}"[:2000]),
    }


def _patch(client: httpx.Client, token: str, page_id: str, props: dict) -> None:
    resp = client.patch(f"{API}/pages/{page_id}", headers=_headers(token),
                        json={"properties": props}, timeout=30)
    resp.raise_for_status()


async def enrich(token: str, db_id: str, profile: str, config: dict,
                 page_fetcher=fetch_page_text) -> tuple[int, int]:
    """보강 대상을 찾아 채점·되쓰기하고 (성공, 실패) 건수를 반환한다.

    page_fetcher는 테스트에서 주입할 수 있도록 분리했다(기본은 실제 HTTP fetch).
    """
    today = datetime.date.today().isoformat()
    ok = fail = 0
    with httpx.Client() as client:
        resp = client.post(f"{API}/databases/{db_id}/query", headers=_headers(token),
                          json={"filter": build_query_filter(), "page_size": 50},
                          timeout=30)
        resp.raise_for_status()
        pending = extract_pending(resp.json())
        for item in pending:
            page_id, url = item["page_id"], item["url"]
            try:
                text = page_fetcher(url)
                if not text.strip():
                    raise RuntimeError("페이지 본문이 비어 있음(JS 렌더링/차단 가능)")
                scored = await score_text(url, text, profile, config)
                _patch(client, token, page_id,
                       build_enrich_update(scored, url, today, item["title_empty"]))
                ok += 1
            except Exception as e:  # 한 건 실패가 전체를 막지 않는다
                try:
                    _patch(client, token, page_id, build_failure_update(str(e)))
                except Exception:
                    pass  # 실패 표시마저 실패하면 다음 실행에서 재시도
                fail += 1
    return ok, fail

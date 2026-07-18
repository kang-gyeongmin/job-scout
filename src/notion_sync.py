"""Notion 데이터베이스 연동 — 새로 채점된 공고를 매일 DB에 쌓는다.

.env에 NOTION_TOKEN(통합 시크릿)과 NOTION_DB_ID가 모두 있을 때만 동작한다.
DB는 scripts/setup_notion.py로 한 번 만들면 되고, 스키마는 아래
PROPERTIES와 일치해야 한다. HistoryStore.add()가 반환한 "새로 추가된
항목"만 올리므로 중복 페이지가 생기지 않는다.
"""
import time

import httpx

from src.mailer import SITE_LABEL

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
STATUS_OPTIONS = ["신규", "관심", "지원함", "제외"]

# DB 생성(setup 스크립트)과 페이지 생성(build_page)이 공유하는 스키마
PROPERTIES = {
    "제목": {"title": {}},
    "회사": {"rich_text": {}},
    "사이트": {"select": {}},
    "점수": {"number": {}},
    "상태": {"select": {"options": [
        {"name": s, "color": c} for s, c in
        zip(STATUS_OPTIONS, ("blue", "yellow", "green", "gray"))]}},
    "수집일": {"date": {}},
    "이유": {"rich_text": {}},
    "요약": {"rich_text": {}},
    "링크": {"url": {}},
    "공고 ID": {"rich_text": {}},
}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _text(value: str) -> dict:
    # rich_text 한 블록은 2000자 제한 — 요약이 넘는 경우 잘라 보낸다
    return {"rich_text": [{"text": {"content": (value or "")[:2000]}}]}


def build_page(entry: dict, db_id: str) -> dict:
    """history 항목 하나를 Notion 페이지 생성 요청 본문으로 변환한다."""
    return {
        "parent": {"database_id": db_id},
        "properties": {
            "제목": {"title": [{"text": {"content": entry["title"][:2000]}}]},
            "회사": _text(entry["company"]),
            "사이트": {"select": {"name": SITE_LABEL.get(entry["site"], entry["site"])}},
            "점수": {"number": entry["score"]},
            "상태": {"select": {"name": "신규"}},
            "수집일": {"date": {"start": entry["date"]}},
            "이유": _text(entry["reason"]),
            "요약": _text(entry["summary"]),
            "링크": {"url": entry["url"]},
            "공고 ID": _text(entry["id"]),
        },
    }


def sync(entries: list[dict], token: str, db_id: str) -> int:
    """새 항목들을 Notion DB에 페이지로 추가하고 성공 건수를 반환한다."""
    created = 0
    with httpx.Client() as client:
        for entry in entries:
            if created:
                time.sleep(0.4)  # Notion rate limit (평균 3 req/s)
            resp = client.post(f"{API}/pages", headers=_headers(token),
                               json=build_page(entry, db_id), timeout=30)
            resp.raise_for_status()
            created += 1
    return created


def create_database(token: str, parent_page_id: str) -> str:
    """parent 페이지 아래에 job-scout DB를 만들고 그 id를 반환한다."""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"text": {"content": "job-scout 채용 공고"}}],
        "properties": PROPERTIES,
    }
    resp = httpx.post(f"{API}/databases", headers=_headers(token),
                      json=body, timeout=30)
    resp.raise_for_status()
    return resp.json()["id"]

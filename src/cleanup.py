"""모집 마감일이 지난 노션 공고를 정리(아카이브)한다.

매일 실행(src.main)에 포함되어, 마감일이 '오늘 이전'인 공고를 노션 휴지통으로
보낸다. 마감일이 없는 공고(상시채용 등)는 대상이 아니다. 아카이브는 되돌릴 수
있다(노션 휴지통 보관).
"""
import datetime
import time

import httpx

from src.notion_sync import API, _headers


def build_expired_filter(today: str) -> dict:
    """마감일이 today보다 이전인(=마감된) 공고 조회 필터.

    Notion date의 'before'는 경계값 미포함이므로, 오늘 마감(오늘==마감일)인
    공고는 남고 어제까지 마감인 공고만 걸린다.
    """
    return {"property": "마감일", "date": {"before": today}}


def find_expired(token: str, db_id: str, today: str) -> list[str]:
    """마감일이 지난 페이지 id 목록을 반환한다(페이지네이션 처리)."""
    ids: list[str] = []
    payload = {"filter": build_expired_filter(today), "page_size": 100}
    with httpx.Client() as client:
        while True:
            resp = client.post(f"{API}/databases/{db_id}/query", headers=_headers(token),
                              json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            ids.extend(p["id"] for p in data.get("results", []))
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]
    return ids


def cleanup_expired(token: str, db_id: str, today: str | None = None) -> int:
    """마감 지난 공고를 아카이브하고 처리 건수를 반환한다."""
    today = today or datetime.date.today().isoformat()
    ids = find_expired(token, db_id, today)
    with httpx.Client() as client:
        for i, page_id in enumerate(ids):
            if i:
                time.sleep(0.34)  # Notion rate limit
            resp = client.patch(f"{API}/pages/{page_id}", headers=_headers(token),
                               json={"archived": True}, timeout=30)
            resp.raise_for_status()
    return len(ids)

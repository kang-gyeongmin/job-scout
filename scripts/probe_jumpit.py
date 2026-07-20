"""점핏 내부 API 프로빙 — JSON으로 공고 목록을 받을 수 있는지 확인."""
import json

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://www.jumpit.co.kr/",
}

# 점핏 채용 검색 내부 API 후보 (관찰된 구조: /api/positions)
CANDIDATES = [
    ("https://api.jumpit.co.kr/api/positions",
     {"sort": "rsp_rate", "keyword": "데이터 엔지니어"}),
    ("https://www.jumpit.co.kr/api/positions",
     {"sort": "rsp_rate", "keyword": "데이터 엔지니어"}),
]

for url, params in CANDIDATES:
    print(f"\n=== {url} params={params}")
    try:
        r = httpx.get(url, params=params, headers=HEADERS, timeout=15,
                      follow_redirects=True)
        print("status:", r.status_code, "ctype:", r.headers.get("content-type"))
        if r.status_code == 200 and "json" in (r.headers.get("content-type") or ""):
            data = r.json()
            print("top-level keys:", list(data)[:10] if isinstance(data, dict)
                  else type(data))
            # 목록 위치 추정
            positions = (data.get("result", {}).get("positions")
                         if isinstance(data, dict) else None)
            if positions is None and isinstance(data, dict):
                positions = data.get("positions") or data.get("result")
            print("count:", len(positions) if isinstance(positions, list) else "?")
            if isinstance(positions, list) and positions:
                first = positions[0]
                print("first item keys:", list(first))
                print(json.dumps(first, ensure_ascii=False, indent=1)[:1500])
        else:
            print("body head:", r.text[:300])
    except Exception as e:
        print("ERROR:", type(e).__name__, e)

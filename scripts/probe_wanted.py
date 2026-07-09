"""원티드 내부 API 응답을 확인하고 테스트 fixture로 저장한다."""
import json
from pathlib import Path

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.wanted.co.kr/",
}
PARAMS = {
    "country": "kr",
    "job_sort": "job.latest_order",
    "locations": "seoul.all",
    "years": 0,        # 경력 하한
    "limit": 20,
    "query": "데이터 엔지니어",
}

resp = httpx.get("https://www.wanted.co.kr/api/v4/jobs",
                 params=PARAMS, headers=HEADERS, timeout=15)
resp.raise_for_status()
data = resp.json()
out = Path("tests/fixtures/wanted_list.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"저장: {out}, 공고 수: {len(data.get('data', []))}")
print(json.dumps(data["data"][0], ensure_ascii=False, indent=1)[:2000])

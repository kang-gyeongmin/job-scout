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
    # years는 경력 하한이 아니라 단일 연차 매칭 필터:
    # annual_from <= years <= annual_to 인 공고만 반환된다.
    # years=3이면 신입 허용(annual_from=0) 공고와 1~3년 최소 경력 공고가 섞여
    # 나와, 재생성된 fixture가 신입 외 experience 분기도 커버한다.
    "years": 3,
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

"""로켓펀치 채용 검색 HTML 확인 및 fixture 저장."""
from pathlib import Path

import httpx

resp = httpx.get("https://www.rocketpunch.com/jobs", params={
    "keywords": "데이터 엔지니어",
    "hiring_types": 0,   # 정규직 (probe 결과에 따라 조정)
}, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    timeout=15, follow_redirects=True)
resp.raise_for_status()
Path("tests/fixtures/rocketpunch_list.html").write_text(resp.text, encoding="utf-8")
print(f"상태: {resp.status_code}, 길이: {len(resp.text)}")
print("공고 카드로 보이는 요소를 브라우저 개발자도구/파일에서 확인할 것")

"""사람인 수집기 — 오픈 API(job-search) 사용.

https://oapi.saramin.co.kr/job-search 는 키 발급만 하면 쓸 수 있는 공식 API라
스크래핑이 필요 없다. 키는 .env의 SARAMIN_API_KEY로 주입한다.

경력 필터: exp_cd는 단일 구분값(1=신입, 2=경력)이라 "신입~3년"을 한 번에
표현할 수 없다. 원티드 수집기와 같은 방식으로 두 번 조회해 합친다:
- exp_cd=1 (신입)
- exp_cd=2 & exp_max=3 (경력 3년 이하)

상세 본문 API는 제공되지 않으므로 description에는 목록 응답의 keyword·업종·
고용형태·급여를 모아 채점 참고용으로 넣는다.
"""
import datetime
import html
import os
import time

import httpx

from src.models import JobPosting

BASE = "https://oapi.saramin.co.kr/job-search"
# 서울/경기/인천 상위 지역 코드 (사람인 2차 지역코드 문서 기준)
LOC_CD = "101000,102000,108000"


def _clean(text: str) -> str:
    """API가 회사명·지역명에 HTML 엔티티(&gt; 등)를 섞어 보내는 경우 정리."""
    return html.unescape(text or "").strip()


def _ts_to_date(ts: str) -> str:
    """unix 타임스탬프 문자열을 ISO 날짜로. 형식이 다르면 빈 문자열."""
    try:
        return datetime.date.fromtimestamp(int(ts)).isoformat()
    except (TypeError, ValueError):
        return ""


def parse_list(data: dict) -> list[JobPosting]:
    postings = []
    for item in data.get("jobs", {}).get("job", []):
        position = item.get("position", {})
        desc_parts = [
            item.get("keyword", ""),
            position.get("industry", {}).get("name", ""),
            position.get("job-type", {}).get("name", ""),
            item.get("salary", {}).get("name", ""),
        ]
        postings.append(JobPosting(
            id=f"saramin:{item['id']}",
            site="saramin",
            title=_clean(position.get("title", "")),
            company=_clean(item.get("company", {}).get("detail", {}).get("name", "")),
            location=_clean(position.get("location", {}).get("name", "")),
            experience=position.get("experience-level", {}).get("name", ""),
            url=item.get("url", ""),
            description=" / ".join(p for p in desc_parts if p),
            posted_at=(item.get("posting-date", "") or "")[:10],
            deadline=_ts_to_date(item.get("expiration-timestamp", "")),
        ))
    return postings


def search(keyword: str, limit: int = 20) -> list[JobPosting]:
    """신입~3년 필터가 적용된 사람인 공고를 검색한다.

    신입(exp_cd=1)과 경력 3년 이하(exp_cd=2, exp_max=3)를 각각 조회해
    id 기준으로 중복 제거하며 합친다 (신입 결과가 앞). 오픈 API는 일일
    호출 한도가 있으므로 호출 사이에 0.5초 지연을 둔다.
    """
    api_key = os.environ.get("SARAMIN_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("SARAMIN_API_KEY가 없습니다 — .env에 설정 후 "
                           "config.yaml에서 saramin을 활성화하세요")

    base_params = {
        "access-key": api_key,
        "keywords": keyword,
        "loc_cd": LOC_CD,
        "sort": "pd",  # 등록일순
        "count": limit,
        "fields": "posting-date,keyword-code",
    }
    exp_filters = ({"exp_cd": 1}, {"exp_cd": 2, "exp_max": 3})
    merged: dict[str, JobPosting] = {}
    with httpx.Client() as client:
        for i, exp in enumerate(exp_filters):
            if i > 0:
                time.sleep(0.5)  # rate limit (호출 사이)
            resp = client.get(BASE, params={**base_params, **exp},
                              headers={"Accept": "application/json"}, timeout=15)
            resp.raise_for_status()
            for p in parse_list(resp.json()):
                if p.id not in merged:
                    merged[p.id] = p
    return list(merged.values())[:limit]

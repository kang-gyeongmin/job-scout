"""원티드 수집기 — 내부 JSON API(v4) 사용. 개인 용도 소량 수집.

probe 결과(scripts/probe_wanted.py, tests/fixtures/wanted_list.json)로 확인한 실제
목록 응답 구조는 브리프가 가정한 구조와 대부분 일치했다. 유일한 차이:
목록 응답 각 항목에 `annual_from`/`annual_to` (경력 하한/상한, 년 단위)가 포함되어
있어 "목록 응답에는 경력 정보 없음"이라는 브리프의 가정과 달리 experience 필드를
채울 수 있다. 상세 응답(`/api/v4/jobs/{id}`)의 `job.detail.{intro,main_tasks,
requirements}` 구조는 브리프 예상과 동일했다 (덤으로 `preferred_points`도 존재해
description에 포함시켰다).
"""
import time

import httpx

from src.models import JobPosting

BASE = "https://www.wanted.co.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.wanted.co.kr/",
}


def _format_experience(item: dict) -> str:
    """annual_from/annual_to(경력 하한/상한, 년)를 사람이 읽을 문자열로 변환.

    annual_to == 100은 원티드가 상한 없음("경력무관")을 나타내는 sentinel 값으로
    관찰되어 "무관"으로 표기한다.
    """
    from_ = item.get("annual_from")
    to_ = item.get("annual_to")
    if from_ is None or to_ is None:
        return ""
    from_label = "신입" if from_ == 0 else f"{from_}년"
    to_label = "무관" if to_ >= 100 else f"{to_}년"
    return f"{from_label}~{to_label}"


def parse_list(data: dict) -> list[JobPosting]:
    postings = []
    for item in data.get("data", []):
        job_id = item["id"]
        postings.append(JobPosting(
            id=f"wanted:{job_id}",
            site="wanted",
            title=item.get("position", ""),
            company=item.get("company", {}).get("name", ""),
            location=item.get("address", {}).get("location", ""),
            experience=_format_experience(item),
            url=f"{BASE}/wd/{job_id}",
            description="",
            posted_at="",  # 목록 응답에는 등록일이 없음(due_time은 마감일)
        ))
    return postings


def fetch_detail(job_id: int, client: httpx.Client) -> str:
    """상세 본문(소개·주요 업무·자격 요건·우대 사항)을 가져온다. 실패하면 빈 문자열."""
    try:
        resp = client.get(f"{BASE}/api/v4/jobs/{job_id}", headers=HEADERS, timeout=15)
        resp.raise_for_status()
        detail = resp.json().get("job", {}).get("detail", {})
        parts = [detail.get(k, "") for k in
                 ("intro", "main_tasks", "requirements", "preferred_points")]
        return "\n\n".join(p for p in parts if p)
    except httpx.HTTPError:
        return ""


def search(keyword: str, limit: int = 20) -> list[JobPosting]:
    """신입~3년 필터가 적용된 원티드 공고를 검색한다.

    원티드 내부 API의 `years` 파라미터는 범위가 아니라 "이 연차의 지원자를
    받는 공고인가"를 나타내는 단일 값 필터다 (annual_from <= years <= annual_to
    인 공고만 반환). 목록 호출은 요청당 1회만 허용되므로(rate limit) years=0,
    1, 2, 3을 각각 조회해 합칠 수 없다. years=0(완전 신입만, annual_from==0인
    공고만 반환)을 쓰면 "1~3년차 최소 경력"을 요구하는 공고가 모두 제외되어
    "신입~3년" 요구사항보다 좁아진다. 대신 years=3을 쓰면 annual_from이
    0~3 사이인 공고를 폭넓게 포함하면서 상한(3년차까지 지원 가능한 공고)도
    자연스럽게 만족해, 단일 호출로 "신입~3년" 요구를 가장 잘 근사한다.
    """
    params = {
        "country": "kr",
        "job_sort": "job.latest_order",
        "locations": "seoul.all",
        "years": 3,
        "limit": limit,
        "query": keyword,
    }
    with httpx.Client() as client:
        resp = client.get(f"{BASE}/api/v4/jobs", params=params,
                          headers=HEADERS, timeout=15)
        resp.raise_for_status()
        postings = parse_list(resp.json())
        for p in postings:
            time.sleep(0.5)  # rate limit
            p.description = fetch_detail(int(p.id.split(":")[1]), client)
    return postings

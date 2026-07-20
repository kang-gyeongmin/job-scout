"""원티드 수집기 — 내부 JSON API(v4) 사용. 개인 용도 소량 수집.

probe 결과(scripts/probe_wanted.py, tests/fixtures/wanted_list.json)로 확인한 실제
목록 응답 구조는 브리프가 가정한 구조와 대부분 일치했다. 유일한 차이:
목록 응답 각 항목에 `annual_from`/`annual_to` (경력 하한/상한, 년 단위)가 포함되어
있어 "목록 응답에는 경력 정보 없음"이라는 브리프의 가정과 달리 experience 필드를
채울 수 있다. 상세 응답(`/api/v4/jobs/{id}`)의 `job.detail.{intro,main_tasks,
requirements}` 구조는 브리프 예상과 동일했다 (덤으로 `preferred_points`도 존재해
description에 포함시켰다).

`years` 파라미터는 경력 범위가 아니라 단일 연차 매칭 필터(annual_from <= years
<= annual_to)이므로, "신입~3년"을 커버하기 위해 search()는 years=0과 years=3
목록을 각각 조회해 id 기준으로 합친다 (자세한 근거는 search() 독스트링 참고).
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


def parse_list(data: dict,
               max_experience_from: int | None = None) -> list[JobPosting]:
    """목록 응답을 JobPosting으로 변환한다.

    max_experience_from를 주면 최소 요구 경력(annual_from)이 그 값을 초과하는
    공고를 버린다 — 예: 1이면 "2년~5년"·"3년~10년"처럼 신입/주니어가 지원할
    수 없는 공고를 제외한다. annual_from이 없으면(경력 정보 없음) 남긴다.
    """
    postings = []
    for item in data.get("data", []):
        annual_from = item.get("annual_from")
        if (max_experience_from is not None and annual_from is not None
                and annual_from > max_experience_from):
            continue
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
            posted_at="",  # 목록 응답에는 등록일이 없음
            deadline=(item.get("due_time") or "")[:10],  # 상시채용이면 null
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
    except (httpx.HTTPError, ValueError):
        # ValueError: 응답이 200이지만 본문이 JSON이 아닌 경우 —
        # 해당 공고 하나만 description=""로 처리하고 전체 수집은 계속한다.
        return ""


def search(keyword: str, limit: int = 20,
           max_experience_from: int = 1) -> list[JobPosting]:
    """신입~3년 필터가 적용된 원티드 공고를 검색한다.

    max_experience_from는 "지원 가능한 최소 요구 경력" 상한이다 (기본 1년).
    years=3 목록에는 annual_from이 1~3인 공고가 섞여 들어오는데, 그중 최소
    경력이 이 값을 넘는 공고(예: annual_from==3인 "3년~10년")는 신입/주니어가
    지원할 수 없으므로 parse_list 단계에서 버린다.

    원티드 내부 API의 `years` 파라미터는 범위가 아니라 "이 연차의 지원자가
    지원 가능한 공고인가"를 뜻하는 단일 값 매칭 필터다 (annual_from <= years
    <= annual_to 인 공고만 반환). 단일 값으로는 "신입~3년"을 재현할 수 없다:

    - years=0 만 쓰면 annual_from == 0(완전 신입 허용) 공고만 남아
      최소 1~3년 경력을 요구하는 주니어 공고가 빠지고,
    - years=3 만 쓰면 annual_from == 3(신입 지원 불가) 공고까지 섞인다.

    그래서 목록을 두 번(years=0, years=3) 호출해 id 기준으로 중복 제거하며
    합친다 (years=0 결과가 앞). 합친 목록을 `limit` 건으로 자른 **뒤에만**
    상세를 조회하므로 총 요청 수는 목록 2회 + 상세 최대 `limit`회이고,
    모든 요청 사이에 0.5초 지연을 둔다.
    """
    base_params = {
        "country": "kr",
        "job_sort": "job.latest_order",
        # 리스트는 locations=...&locations=... 반복 파라미터로 인코딩된다
        "locations": ["seoul.all", "gyeonggi.all", "incheon.all"],
        "limit": limit,
        "query": keyword,
    }
    merged: dict[str, JobPosting] = {}
    with httpx.Client() as client:
        for i, years in enumerate((0, 3)):
            if i > 0:
                time.sleep(0.5)  # rate limit (목록 호출 사이)
            resp = client.get(f"{BASE}/api/v4/jobs",
                              params={**base_params, "years": years},
                              headers=HEADERS, timeout=15)
            resp.raise_for_status()
            for p in parse_list(resp.json(), max_experience_from):
                if p.id not in merged:
                    merged[p.id] = p
        postings = list(merged.values())[:limit]  # 상세 조회 전에 limit로 절단
        for p in postings:
            time.sleep(0.5)  # rate limit
            p.description = fetch_detail(int(p.id.split(":")[1]), client)
    return postings

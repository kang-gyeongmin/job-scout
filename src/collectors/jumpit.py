"""점핏(Jumpit) 수집기 — 사람인 계열 개발자 특화 채용, 내부 JSON API 사용.

probe(scripts/probe_jumpit.py, 2026-07-20): https://api.jumpit.co.kr/api/positions
가 WAF 차단 없이 JSON을 반환한다. 목록 각 항목에 minCareer/maxCareer(최소·최대
요구 경력, 년)와 newcomer(신입 여부)가 있어 경력 필터를 코드에서 적용할 수 있다
(원티드 annual_from/annual_to와 같은 개념).

- keyword 파라미터는 무시한다: 프로빙 결과 keyword는 실제 검색어로 동작하지
  않고(어떤 개발 키워드를 넣어도 개발 공고 전체 611건이 반환됨), 점핏은 직무
  카테고리(jobCategory, 콤마 구분 ID)로 필터링한다. work24 수집기와 같은 방식
  으로 keyword 대신 데이터 직무 카테고리로 전량 수집한다.
    · 19=빅데이터 엔지니어 (기본값)
    · 8=인공지능/머신러닝, 1=서버/백엔드, 9=devops/시스템, 7=DBA (필요 시 넓히기)
- 관련도순이라 고경력 공고도 섞여 오므로, 최소 경력(minCareer)이
  max_experience_from을 넘는 공고는 버린다.
- 지역은 목록에 "서울 구로구"처럼 들어온다. 수도권(서울·경기·인천)만 남기되,
  지역 정보가 없는 공고(재택·전국 등)는 남긴다.
- 상세 본문 API는 쓰지 않고, 채점 참고용으로 직무 카테고리·기술스택·지역을
  description에 담는다 (사람인 수집기와 같은 방식).
- 목록은 페이지당 16건. limit을 채울 때까지 page를 넘기며 모은다.
"""
import time

import httpx

from src.models import JobPosting

API = "https://api.jumpit.co.kr/api/positions"
BASE = "https://jumpit.saramin.co.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Referer": "https://www.jumpit.co.kr/",
}
PAGE_SIZE = 16          # 관찰된 페이지당 건수
MAX_PAGES = 5           # 안전 상한
LOC_PREFIXES = ("서울", "경기", "인천")  # 수도권 필터
DEFAULT_CATEGORIES = "19"  # 빅데이터 엔지니어 (8=AI/ML 등은 config에서 확장)


def _format_experience(item: dict) -> str:
    """minCareer/maxCareer(최소·최대 경력, 년)를 사람이 읽을 문자열로 변환."""
    lo = item.get("minCareer")
    hi = item.get("maxCareer")
    if item.get("newcomer") or (lo == 0 and hi == 0):
        return "신입"
    if lo is None or hi is None:
        return ""
    lo_label = "신입" if lo == 0 else f"{lo}년"
    return f"{lo_label}~{hi}년"


def _in_capital_area(locations: list[str]) -> bool:
    """지역이 비어 있거나(재택·전국) 수도권을 하나라도 포함하면 True."""
    if not locations:
        return True
    return any(loc.startswith(LOC_PREFIXES) for loc in locations)


def parse_list(data: dict,
               max_experience_from: int | None = None) -> list[JobPosting]:
    """API 응답을 JobPosting으로 변환한다.

    max_experience_from를 주면 최소 요구 경력(minCareer)이 그 값을 초과하는
    공고를 버린다 (예: 1이면 minCareer가 2 이상인 공고 제외). 수도권 밖 공고도
    함께 제외한다.
    """
    postings = []
    for item in data.get("result", {}).get("positions", []):
        min_career = item.get("minCareer")
        if (max_experience_from is not None and min_career is not None
                and min_career > max_experience_from):
            continue
        locations = item.get("locations") or []
        if not _in_capital_area(locations):
            continue
        job_id = item["id"]
        desc_parts = [
            item.get("jobCategory", ""),
            ", ".join(item.get("techStacks") or []),
            ", ".join(locations),
        ]
        postings.append(JobPosting(
            id=f"jumpit:{job_id}",
            site="jumpit",
            title=item.get("title", ""),
            company=item.get("companyName", ""),
            location=", ".join(locations),
            experience=_format_experience(item),
            url=f"{BASE}/position/{job_id}",
            description=" / ".join(p for p in desc_parts if p),
            posted_at="",  # 목록 응답에는 등록일이 없음
            deadline=("" if item.get("alwaysOpen")
                      else (item.get("closedAt") or "")[:10]),
        ))
    return postings


def search(keyword: str, limit: int = 20, max_experience_from: int = 1,
           categories: str = DEFAULT_CATEGORIES) -> list[JobPosting]:
    """신입/주니어(minCareer <= max_experience_from) 점핏 공고를 수집한다.

    keyword는 무시하고 categories(jobCategory ID, 콤마 구분)로 필터링한다
    (모듈 독스트링 참고). 필터를 통과한 공고가 limit에 찰 때까지 page를
    넘기며 모은다 (최대 MAX_PAGES 페이지). 요청 사이에 0.5초 지연을 둔다.
    """
    merged: dict[str, JobPosting] = {}
    with httpx.Client() as client:
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                time.sleep(0.5)  # rate limit (페이지 호출 사이)
            resp = client.get(API, params={"jobCategory": categories,
                                           "page": page},
                              headers=HEADERS, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            page_postings = parse_list(data, max_experience_from)
            for p in page_postings:
                if p.id not in merged:
                    merged[p.id] = p
            if len(merged) >= limit:
                break
            # 마지막 페이지(더 이상 결과 없음)면 중단
            result = data.get("result", {})
            if len(result.get("positions", [])) < PAGE_SIZE:
                break
    return list(merged.values())[:limit]

"""직행(zighang) 수집기 — 신입 채용 특화, 내부 JSON API 사용.

probe(scripts/probe_zighang.py, 2026-08-01): https://api.zighang.com/api/recruitments
가 WAF·인증 없이 페이지네이션 JSON을 반환한다(총 10만+건, 고용24 등 집계).
필터 파라미터가 필드명과 일치한다:
  depthOnes(직무 대분류)·regions(지역)·careerMin/careerMax(경력)·keyword·
  employeeTypes·educations·page·size

직무 카테고리(/recruitments/job-categories): IT_개발(IT·개발), AI_데이터(AI·데이터).
careerMin=0 은 신입 지원 가능 공고를 뜻한다. 지역은 수도권 고정, careerMax로
경력 상한(신입~N년)을 준다. 상세 조회 없이 목록만으로 필드가 충분하다
(기업규모는 제공하지 않음).
"""
import httpx

from src.models import JobPosting

LIST_API = "https://api.zighang.com/api/recruitments"
DETAIL_URL = "https://zighang.com/recruitment/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/144.0.0.0 Safari/537.36",
           "Accept": "application/json", "Origin": "https://zighang.com",
           "Referer": "https://zighang.com/"}
DEFAULT_CATEGORIES = "IT_개발,AI_데이터"  # 직무 대분류(depthOnes)
REGIONS = "서울,경기,인천"                # 수도권 고정


def _format_experience(lo, hi) -> str:
    """careerMin/careerMax(경력, 년)를 사람이 읽을 문자열로."""
    if lo is None:
        return ""
    lo_label = "신입" if lo == 0 else f"{lo}년"
    if hi is None or hi == lo:
        return lo_label
    hi_label = "무관" if hi >= 100 else f"{hi}년"
    return f"{lo_label}~{hi_label}"


def parse_list(data: dict) -> list[JobPosting]:
    """recruitments 응답을 JobPosting 목록으로 변환한다."""
    postings = []
    for it in data.get("data", {}).get("content", []):
        uuid = it.get("id")
        if not uuid:
            continue
        regions = it.get("regions") or []
        desc_parts = [
            ", ".join(it.get("depthTwos") or []),
            ", ".join(it.get("employeeTypes") or []),
            ", ".join((it.get("keywords") or [])[:5]),
            f"출처: {it['affiliate']}" if it.get("affiliate") else "",
        ]
        postings.append(JobPosting(
            id=f"zighang:{uuid}",
            site="zighang",
            title=it.get("title", ""),
            company=(it.get("company") or {}).get("name", ""),
            location=", ".join(regions),
            experience=_format_experience(it.get("careerMin"), it.get("careerMax")),
            url=DETAIL_URL.format(uuid),
            description=" / ".join(p for p in desc_parts if p),
            posted_at=(it.get("createdAt", "") or "")[:10],
            deadline=(it.get("endDate", "") or "")[:10],
        ))
    return postings


def search(keyword: str, limit: int = 20, max_experience_from: int = 1,
           categories: str = DEFAULT_CATEGORIES) -> list[JobPosting]:
    """수도권 신입(careerMin=0) IT·데이터 공고를 수집한다(keyword 무시).

    careerMax로 경력 상한(신입~max_experience_from년)을 준다. depthOnes는
    categories로 조정할 수 있다. 목록 한 페이지(size=limit)만 받는다.
    """
    params = {
        "page": 0, "size": limit, "depthOnes": categories, "regions": REGIONS,
        "careerMin": 0, "careerMax": max_experience_from,
    }
    with httpx.Client() as client:
        resp = client.get(LIST_API, params=params, headers=HEADERS, timeout=15,
                         follow_redirects=True)
        resp.raise_for_status()
        return parse_list(resp.json())[:limit]

"""잡코리아(jobkorea.co.kr) 수집기 — 중견·대기업 포함 폭넓은 커버리지.

probe(scripts/probe_jobkorea.py, 2026-08-01): 검색 페이지가 WAF 없이 서버 렌더
HTML을 반환한다(안티봇 신호 없음). 새 Tailwind 디자인이라 카드 CSS 클래스는
깨지기 쉬우므로, 검색 HTML에서는 공고 ID(/Recruit/GI_Read/{id})만 뽑고 나머지
필드는 상세 페이지의 **안정적인 og 태그**에서 파싱한다:

- og:title    "{회사} 채용 - {제목} | 잡코리아"
- og:description "경력 : 신입 , 학력 : ... , 급여 : ... , 마감일 : 2026.10.19"
- 기업구분 라벨 → 값 span: 기업규모(중소기업/중견기업/대기업) — 캐치와 같은
  company_size 정보

keyword 검색(stext)으로 받고, 신입 지원 가능 공고만 남긴다(경력에 '신입'/'무관').
"""
import re
import time

import httpx
from bs4 import BeautifulSoup

from src.models import JobPosting

BASE = "https://www.jobkorea.co.kr"
SEARCH_URL = BASE + "/Search/"
DETAIL_URL = BASE + "/Recruit/GI_Read/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/144.0.0.0 Safari/537.36",
           "Accept-Language": "ko-KR,ko;q=0.9"}
MAX_DETAILS = 40  # 상세 조회 상한(신입 필터로 걸러지므로 limit보다 넉넉히)


def parse_search_ids(html: str) -> list[str]:
    """검색 HTML에서 공고 ID를 등장 순서대로 중복 없이 뽑는다."""
    seen, ids = set(), []
    for m in re.finditer(r"/Recruit/GI_Read/(\d+)", html):
        jid = m.group(1)
        if jid not in seen:
            seen.add(jid)
            ids.append(jid)
    return ids


def _field(desc: str, label: str) -> str:
    """og:description('경력 : 신입 , 급여 : ...')에서 label 값을 뽑는다."""
    m = re.search(rf"{label}\s*:\s*([^,]+?)(?:\s*,|$)", desc)
    return m.group(1).strip() if m else ""


def _to_iso(date_text: str) -> str:
    """'2026.10.19' 또는 '2026.10.19(월) 채용 시 마감' → '2026-10-19'. 없으면 ''."""
    m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", date_text or "")
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def parse_detail(html: str, job_id: str) -> JobPosting:
    """상세 HTML을 JobPosting으로. 회사·제목은 og:title, 경력·급여·마감일은
    og:description, 기업규모는 '기업구분' 라벨에서 뽑는다."""
    soup = BeautifulSoup(html, "html.parser")
    og_title = _meta(soup, "og:title")
    og_desc = _meta(soup, "og:description")

    # "{회사} 채용 - {제목} | 잡코리아"
    m = re.match(r"^(.*?) 채용 - (.*?)(?:\s*\|\s*잡코리아)?$", og_title)
    company = m.group(1).strip() if m else ""
    title = m.group(2).strip() if m else og_title

    experience = _field(og_desc, "경력")
    salary = _field(og_desc, "급여")
    deadline = _to_iso(_field(og_desc, "마감일"))

    company_size = ""
    # 정확 매칭으로 보이는 라벨 span만 잡는다(스크립트 blob 안의 '기업구분' 제외)
    size_text = soup.find(string=re.compile(r"^\s*기업구분\s*$"))
    if size_text:
        span = size_text.parent
        sib = span.find_next_sibling() or (span.parent.find_next_sibling()
                                           if span.parent else None)
        if sib:
            # "중소기업 (비상장)" → "중소기업"
            company_size = sib.get_text(strip=True).split("(")[0].strip()

    desc_parts = [p for p in (f"급여: {salary}" if salary else "", og_desc) if p]
    return JobPosting(
        id=f"jobkorea:{job_id}",
        site="jobkorea",
        title=title,
        company=company,
        location="",  # 상세 근무지역 마크업이 불안정 — 제목/본문으로 대체
        experience=experience,
        url=DETAIL_URL.format(job_id),
        description=" / ".join(desc_parts),
        posted_at="",
        deadline=deadline,
        company_size=company_size,
    )


def _meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", property=prop)
    return (tag.get("content") or "").strip() if tag else ""


def _is_sinip(experience: str) -> bool:
    """신입 지원 가능(경력에 '신입' 또는 '무관')이면 True."""
    return "신입" in experience or "무관" in experience


def fetch_detail(job_id: str, client: httpx.Client) -> JobPosting | None:
    try:
        resp = client.get(DETAIL_URL.format(job_id), headers=HEADERS, timeout=15,
                          follow_redirects=True)
        resp.raise_for_status()
        return parse_detail(resp.text, job_id)
    except (httpx.HTTPError, ValueError):
        return None


def search(keyword: str, limit: int = 20) -> list[JobPosting]:
    """키워드로 잡코리아 공고를 검색해 신입 지원 가능 건만 수집한다.

    검색 HTML에서 공고 ID를 뽑고, 각 상세를 조회해 필드·기업규모를 채운다.
    신입(경력에 '신입'/'무관')만 남기며, limit에 도달하면 멈춘다. 요청 사이
    0.4초 지연.
    """
    postings: list[JobPosting] = []
    with httpx.Client() as client:
        # careerType=1: 신입 지원 가능 공고로 검색을 좁혀 수율을 높인다
        resp = client.get(SEARCH_URL, params={"stext": keyword, "careerType": "1"},
                         headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        ids = parse_search_ids(resp.text)[:MAX_DETAILS]
        for jid in ids:
            if len(postings) >= limit:
                break
            time.sleep(0.4)  # rate limit
            p = fetch_detail(jid, client)
            if p and _is_sinip(p.experience):
                postings.append(p)
    return postings

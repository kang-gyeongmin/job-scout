"""캐치(catch.co.kr) 수집기 — 중견·대기업·공기업 신입 공채 특화.

probe(scripts/probe_catch.py, 2026-07-25):
- 목록: GET /api/v1.0/recruit/information/getRecruitList 가 WAF·인증 없이 JSON을
  반환한다. 파라미터가 많고(JobCode·Sido·Career·Size·WorkPosition·Sort·curpage·
  pageSize·onRecruitYN 등) 일부가 필수라, 브라우저 Network 탭에서 실제 요청을
  확보해 DEFAULT_PARAMS에 고정했다(work24처럼 keyword 대신 고정 필터로 수집).
- 상세: /NCS/RecruitInfoDetails/{id} 서버 렌더 HTML에 **기업규모(대기업/중견/
  공기업)**가 <li><span class="item">기업규모</span><span class="txt">값</span></li>
  로 노출된다. 목록 JSON엔 기업규모가 없어 상세를 조회해 채운다 —
  이게 원티드·점핏엔 없는 캐치의 핵심 가치다.

DEFAULT_PARAMS(사용자 UI 선택 기준):
  JobCode=0605,0612 (IT 세부직무: 데이터/개발 계열)
  Sido=서울,인천,경기 (수도권) / Career=1,4 (신입 계열)
  Size=1,3,4 (대기업/중견/공기업) / WorkPosition=1,2,4 (고용형태)
  onRecruitYN=Y (모집 중만) / Sort=0 / pageSize=30
필터를 바꾸려면 config.yaml의 catch_params로 개별 키를 덮어쓴다.
"""
import time

import httpx
from bs4 import BeautifulSoup

from src.models import JobPosting

BASE = "https://www.catch.co.kr"
LIST_API = BASE + "/api/v1.0/recruit/information/getRecruitList"
DETAIL_URL = BASE + "/NCS/RecruitInfoDetails/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
API_HEADERS = {**HEADERS, "Accept": "application/json, text/plain, */*",
               "Referer": BASE + "/NCS/RecruitSearch",
               "Origin": BASE, "x-is-pc": "true"}
DEFAULT_PARAMS = {
    "Keyword": "", "JobCode": "0605,0612", "Sido": "서울,인천,경기",
    "Career": "1,4", "JCode": "", "Size": "1,3,4", "EduLevel": "",
    "WorkPosition": "1,2,4", "CompID": "", "GroupCode": "", "Sort": "0",
    "curpage": 1, "pageSize": 30, "onRecruitYN": "Y", "ExceptIDList": "",
}
DESC_ITEMS = ("기업규모", "업종", "매출", "사원수")  # 상세 라벨 중 참고용


def parse_list(data: dict) -> list[JobPosting]:
    """getRecruitList JSON을 JobPosting 목록으로. company_size는 상세에서 채운다."""
    postings = []
    for it in data.get("recruitData", []):
        rid = it.get("RecruitID")
        if rid is None:
            continue
        desc_parts = [
            it.get("Depth", ""),
            f"급여: {it['SalaryText']}" if it.get("SalaryText") else "",
            f"그룹: {it['GroupName']}" if it.get("GroupName") else "",
        ]
        postings.append(JobPosting(
            id=f"catch:{rid}",
            site="catch",
            title=it.get("RecruitTitle", ""),
            company=it.get("CompName", ""),
            location=it.get("WorkArea", ""),
            experience=it.get("CareerGubunCode", ""),  # 예: "신입/경력"
            url=DETAIL_URL.format(rid),
            description=" / ".join(p for p in desc_parts if p),
            posted_at=(it.get("ApplyStartDatetime", "") or "")[:10],
            deadline=(it.get("ApplyEndDatetime", "") or "")[:10],
        ))
    return postings


def _labeled_items(soup: BeautifulSoup) -> dict[str, str]:
    """<li><span class="item">라벨</span><span class="txt">값</span></li> 수집."""
    items = {}
    for li in soup.select("li"):
        label = li.select_one("span.item")
        value = li.select_one("span.txt")
        if label and value:
            items[label.get_text(strip=True)] = value.get_text(strip=True)
    return items


def parse_detail(html: str) -> dict:
    """상세 HTML에서 라벨 항목(기업규모·업종·매출·사원수 등)을 dict로 추출."""
    return _labeled_items(BeautifulSoup(html, "html.parser"))


def fetch_detail_items(recruit_id: str, client: httpx.Client) -> dict:
    """상세 페이지를 받아 라벨 항목 dict를 반환한다. 실패하면 빈 dict."""
    try:
        resp = client.get(DETAIL_URL.format(recruit_id), headers=HEADERS, timeout=15,
                          follow_redirects=True)
        resp.raise_for_status()
        return parse_detail(resp.text)
    except (httpx.HTTPError, ValueError):
        return {}


def search(keyword: str, limit: int = 20,
           params: dict | None = None) -> list[JobPosting]:
    """캐치 신입 공채를 수집한다(keyword 무시, DEFAULT_PARAMS 필터 사용).

    목록을 받은 뒤 각 공고의 상세를 조회해 기업규모(및 업종·매출·사원수)를
    채운다. 요청 사이에 0.4초 지연을 둔다.
    """
    query = {**DEFAULT_PARAMS, **(params or {})}
    with httpx.Client() as client:
        resp = client.get(LIST_API, headers=API_HEADERS, params=query, timeout=15,
                         follow_redirects=True)
        resp.raise_for_status()
        postings = parse_list(resp.json())[:limit]
        for p in postings:
            time.sleep(0.4)  # rate limit (상세 조회 사이)
            items = fetch_detail_items(p.id.split(":")[1], client)
            p.company_size = items.get("기업규모", "")
            extra = " / ".join(f"{k}: {items[k]}" for k in DESC_ITEMS
                               if k != "기업규모" and items.get(k))
            if extra:
                p.description = f"{p.description} / {extra}" if p.description else extra
    return postings

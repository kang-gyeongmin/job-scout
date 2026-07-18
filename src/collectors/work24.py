"""청년 일경험 포털(yw.work24.go.kr) 수집기 — 고용노동부 미래내일 일경험.

probe 결과(2026-07-17): 목록은 POST /d/a/selectWkexPrgmList.do 가 서버 렌더링
HTML을 반환하고 WAF 차단이 없다. 필터 코드는 페이지 체크박스에서 확인:
areaCd 11000=서울, 28000=인천, 41000=경기, 99999=지역무관 / dtyCd 14=IT.

- 검색 keyword 파라미터는 무시한다: 이 사이트는 "IT 직무 + 수도권/지역무관"
  필터로 전량(모집 중) 수집하는 게 목적이고, 프로그램명 검색(pgnm)은 공고
  제목에 직무명이 없는 경우가 많아 오히려 놓친다.
- 기업탐방형(prgmSecd=C)은 1~3일 견학 프로그램이라 제외하고 인턴형(I)·
  프로젝트형(P)·ESG형(E)만 수집한다.
- 상세 페이지는 POST 전용이라 공고별 직링크가 불가능하다. url에는 목록
  페이지를 넣고, 상세 본문(주요내용·모집내용·선발기준)은 수집기가 POST로
  받아 description에 담는다.
"""
import re
import time

from bs4 import BeautifulSoup

import httpx

from src.models import JobPosting

BASE = "https://yw.work24.go.kr"
LIST_URL = f"{BASE}/d/a/selectWkexPrgmList.do"
DETAIL_URL = f"{BASE}/d/a/selectItrnPrjtEsgPrgmDtal.do"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
AREA_CD = "11000,28000,41000,99999"  # 서울, 인천, 경기, 지역무관
DTY_CD = "14"                        # IT
DETAIL_FIELDS = ("프로그램 유형", "일경험 기간", "주요내용",
                 "모집기간", "모집내용", "선발기준내용")


def _fix_year(ymd: str) -> str:
    """목록의 '26-07-10' 형식을 ISO '2026-07-10'으로 변환."""
    m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})", ymd.strip())
    return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def parse_list(html: str) -> list[JobPosting]:
    postings = []
    for card in BeautifulSoup(html, "html.parser").select("div.card"):
        link = card.select_one(".link a[href*='fn_searchDetail']")
        if not link:
            continue
        m = re.search(r"fn_searchDetail\('(\w)','(PG\w+)'\)", link["href"])
        if not m or m.group(1) == "C":  # 기업탐방형은 채용이 아니라 견학
            continue
        fields = {}
        for li in card.select("ul.list li"):
            label = li.select_one("strong")
            if label:
                fields[label.get_text(strip=True)] = (
                    li.get_text(strip=True).removeprefix(label.get_text(strip=True))
                    .replace("​", "").strip())
        type_label = card.select_one(".label i.label-txt")
        recruit_period = fields.get("모집기간", "")
        postings.append(JobPosting(
            id=f"work24:{m.group(2)}",
            site="work24",
            title=link.get_text(strip=True),
            company=fields.get("참여기업") or fields.get("운영기관", ""),
            location=fields.get("지역", ""),
            experience=type_label.get_text(strip=True) if type_label else "",
            url=LIST_URL,  # 상세는 POST 전용이라 직링크 불가 — 목록에서 제목 검색
            description=f"모집기간: {recruit_period} / "
                        f"모집인원: {fields.get('모집인원', '')} / "
                        f"운영기관: {fields.get('운영기관', '')}",
            posted_at=_fix_year(recruit_period.split("~")[0]),
        ))
    return postings


def fetch_detail(program_id: str, client: httpx.Client) -> str:
    """상세(주요내용·모집내용·선발기준 등)를 표에서 추출. 실패하면 빈 문자열."""
    try:
        resp = client.post(DETAIL_URL, data={"untyPrgmCtn": program_id},
                           headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        parts = []
        for th in soup.select("table th"):
            key = th.get_text(strip=True)
            if key in DETAIL_FIELDS and th.find_next_sibling("td"):
                value = th.find_next_sibling("td").get_text("\n", strip=True)
                parts.append(f"{key}: {value}")
        return "\n\n".join(parts)
    except httpx.HTTPError:
        return ""


def search(keyword: str, limit: int = 20) -> list[JobPosting]:
    """모집 중인 IT 직무 일경험 프로그램을 수집한다 (keyword는 무시 — 모듈
    독스트링 참고). 요청 사이에 0.5초 지연을 둔다."""
    data = {
        "areaCd": AREA_CD,
        "dtyCd": DTY_CD,
        "sortOption": "A",
        "recordCountPerPage": limit,
        "currentPageNo": 1,
    }
    with httpx.Client() as client:
        resp = client.post(LIST_URL, data=data, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        postings = parse_list(resp.text)[:limit]
        for p in postings:
            time.sleep(0.5)  # rate limit
            detail = fetch_detail(p.id.split(":")[1], client)
            if detail:
                p.description = f"{p.description}\n\n{detail}"
    return postings

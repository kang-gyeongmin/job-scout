"""캐치(catch.co.kr) 수집기 — 중견·대기업·공기업 신입 공채 특화.

probe(scripts/probe_catch.py, 2026-07-25): 상세 페이지
(www.catch.co.kr/NCS/RecruitInfoDetails/{id})는 WAF 차단 없이 서버 렌더링
HTML을 반환하고, **기업규모(대기업/중견기업/공기업)·업종·매출·사원수**를
`<li><span class="item">라벨</span><span class="txt">값</span></li>` 구조로
노출한다. 이게 이 수집기의 핵심 가치 — 원티드·점핏엔 없는 기업규모 정보다.

목록(공고 ID 수집)은 /NCS/RecruitSearch가 필터(기업형태·직무·신입) 적용 후
AJAX로 로드하는데, 다중 서브도메인 SPA라 목록 API 엔드포인트는 브라우저
Network 탭에서 확인해 SEARCH_API에 채워 넣어야 한다(아래 search 독스트링 참고).
"""
import datetime
import re

import httpx
from bs4 import BeautifulSoup

from src.models import JobPosting

BASE = "https://www.catch.co.kr"
DETAIL_URL = BASE + "/NCS/RecruitInfoDetails/{}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# 상세 라벨 항목 중 description에 담을 것
DESC_ITEMS = ("기업규모", "업종", "매출", "사원수")


def _deadline_from_title(og_title: str) -> str:
    """og:title의 '(~07/28)' 같은 마감 표기를 ISO 날짜로. 없으면 ''.

    연도가 없으므로 오늘 기준으로 추정한다 — 월/일이 오늘보다 과거면 내년으로 본다.
    """
    m = re.search(r"~\s*(\d{1,2})/(\d{1,2})", og_title or "")
    if not m:
        return ""
    month, day = int(m.group(1)), int(m.group(2))
    today = datetime.date.today()
    year = today.year
    try:
        d = datetime.date(year, month, day)
    except ValueError:
        return ""
    if d < today:
        d = d.replace(year=year + 1)
    return d.isoformat()


def _labeled_items(soup: BeautifulSoup) -> dict[str, str]:
    """<li><span class="item">라벨</span><span class="txt">값</span></li> 수집."""
    items = {}
    for li in soup.select("li"):
        label = li.select_one("span.item")
        value = li.select_one("span.txt")
        if label and value:
            items[label.get_text(strip=True)] = value.get_text(strip=True)
    return items


def parse_detail(html: str, recruit_id: str) -> JobPosting:
    """상세 페이지 HTML을 JobPosting으로 변환한다.

    회사(h2.name)·공고명(h1.subj)·기업규모·마감일을 뽑고, 업종·매출·사원수는
    채점 참고용으로 description에 담는다.
    """
    soup = BeautifulSoup(html, "html.parser")
    company_el = soup.select_one("h2.name")
    title_el = soup.select_one("h1.subj")
    company = company_el.get_text(strip=True) if company_el else ""
    title = title_el.get_text(strip=True) if title_el else ""

    items = _labeled_items(soup)
    company_size = items.get("기업규모", "")

    og = soup.find("meta", property="og:title")
    og_title = og.get("content", "") if og else ""

    desc = " / ".join(f"{k}: {items[k]}" for k in DESC_ITEMS if items.get(k))
    # 제목에 신입/경력 표기가 있으면 경력 힌트로 사용
    experience = "신입" if "신입" in title else ("경력" if "경력" in title else "")

    return JobPosting(
        id=f"catch:{recruit_id}",
        site="catch",
        title=title,
        company=company,
        location=items.get("근무지역", ""),
        experience=experience,
        url=DETAIL_URL.format(recruit_id),
        description=desc,
        posted_at="",
        deadline=_deadline_from_title(og_title),
        company_size=company_size,
    )


def fetch_detail(recruit_id: str, client: httpx.Client) -> JobPosting | None:
    """상세 페이지를 받아 JobPosting으로. 실패하면 None(해당 공고만 건너뜀)."""
    try:
        resp = client.get(DETAIL_URL.format(recruit_id), headers=HEADERS, timeout=15,
                          follow_redirects=True)
        resp.raise_for_status()
        return parse_detail(resp.text, recruit_id)
    except (httpx.HTTPError, ValueError):
        return None


def search(keyword: str, limit: int = 20, max_experience_from: int = 1) -> list[JobPosting]:
    """캐치 신입 공채를 수집한다.

    ⚠️ 목록 API 엔드포인트 미확정 — 브라우저 F12 → Network 탭에서
    /NCS/RecruitSearch가 필터 적용 시 호출하는 목록 요청(URL·파라미터·헤더)을
    확인해 여기 채워 넣어야 한다. 확인되면:
      1) 목록 API로 신입 + 중견/대기업/공기업 필터 걸어 recruit_id 목록 수집
      2) 각 id를 fetch_detail로 상세 조회(기업규모 등 확보)
    지금은 엔드포인트가 없어 빈 목록을 반환한다.
    """
    return []

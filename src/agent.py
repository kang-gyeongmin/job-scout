"""Claude Agent SDK 기반 채점 에이전트.

수집기를 커스텀 툴로 노출하고, 에이전트가 키워드를 바꿔가며 검색한 뒤
profile.md 대비 적합도를 JSON으로 출력한다.
"""
import json
import re
from dataclasses import asdict, dataclass
from typing import Callable

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from src.models import JobPosting
from src.store import SeenStore


@dataclass
class ScoredJob:
    id: str
    site: str
    title: str
    company: str
    url: str
    score: int
    reason: str
    summary: str


def build_search_tool(collectors: dict[str, Callable], store: SeenStore,
                      fetched_ids: list[str], failures: list[str]):
    """search_jobs 툴 핸들러를 만든다. (테스트 가능하도록 분리)"""
    async def handler(args: dict) -> dict:
        site, keyword = args["site"], args["keyword"]
        if site not in collectors:
            return {"content": [{"type": "text",
                                 "text": f"사용할 수 없는 사이트: {site}. "
                                         f"가능한 값: {list(collectors)}"}]}
        try:
            postings = store.filter_new(collectors[site](keyword))
        except Exception as e:  # 사이트 단위로만 실패시키고 실행은 계속한다
            msg = f"{site} 수집 실패: {e}"
            if msg not in failures:
                failures.append(msg)
            return {"content": [{"type": "text",
                                 "text": f"{site} 수집 실패 — 이 사이트는 건너뛰어라."}]}
        for p in postings:
            if p.id not in fetched_ids:
                fetched_ids.append(p.id)
        payload = json.dumps([asdict(p) for p in postings], ensure_ascii=False)
        return {"content": [{"type": "text", "text": payload}]}
    return handler


def extract_json(text: str) -> list[dict]:
    """응답 텍스트에서 JSON 배열을 추출한다. 코드 fence 유무 모두 처리."""
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = fence.group(1) if fence else text[text.find("["):text.rfind("]") + 1]
    return json.loads(raw)


SYSTEM_PROMPT = """당신은 채용 공고 매칭 전문가다. search_jobs 툴로 공고를 검색해
지원자 프로필과 비교·채점한다.

규칙:
- 설정에 주어진 키워드로 각 사이트를 검색하고, 결과가 적으면 유사 키워드
  (예: "ETL", "데이터 플랫폼")로 1~2회 추가 검색한다.
- 툴이 반환한 공고만 다룬다. 공고를 지어내지 않는다. url·id는 툴 결과 값을 그대로 쓴다.
- 각 공고에 대해 프로필 대비 적합도 1~10점, 한 줄 이유, 3줄 이내 요약을 만든다.
- 신규 공고가 하나도 없으면 빈 배열 []을 출력한다.

최종 응답은 반드시 아래 형식의 JSON 배열 하나만 출력한다:
```json
[{"id": "...", "site": "...", "title": "...", "company": "...", "url": "...",
  "score": 8, "reason": "...", "summary": "..."}]
```"""


async def run_agent(
    config: dict, profile_text: str, collectors: dict[str, Callable],
    store: SeenStore,
) -> tuple[list[ScoredJob], list[str], list[str]]:
    fetched_ids: list[str] = []
    failures: list[str] = []
    handler = build_search_tool(collectors, store, fetched_ids, failures)
    search_jobs = tool(
        "search_jobs",
        "채용 사이트에서 키워드로 공고를 검색한다. 이미 알림 보낸 공고는 자동 제외된다.",
        {"site": str, "keyword": str},
    )(handler)
    server = create_sdk_mcp_server(name="jobs", version="1.0.0", tools=[search_jobs])

    mission = (
        f"다음 조건으로 신규 채용 공고를 찾아 채점하라.\n"
        f"- 검색 키워드: {config['job_keywords']}\n"
        f"- 사용 가능 사이트: {list(collectors)}\n"
        f"- 대상 경력: {config['experience']}, 지역: {config['locations']}\n\n"
        f"# 지원자 프로필\n{profile_text}"
    )
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"jobs": server},
        allowed_tools=["mcp__jobs__search_jobs"],
        max_turns=15,
    )

    result_text = ""
    async for message in query(prompt=mission, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""

    scored = [ScoredJob(**{k: item[k] for k in
                           ("id", "site", "title", "company", "url",
                            "score", "reason", "summary")})
              for item in extract_json(result_text)] if result_text.strip() else []
    return scored, fetched_ids, failures

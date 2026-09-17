"""진입점: 사람별로 에이전트 수집·채점 → 각자 Notion DB 저장 → (선택) 메일 발송.

config.yaml의 people 목록을 돌며, 각 사람의 프로필·검색조건으로 수집·채점하고
그 사람 전용 Notion DB/데이터 경로에 기록한다. 한 사람이 실패해도 나머지는 계속.
"""
import argparse
import asyncio
import datetime
import functools
import logging
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.agent import run_agent
from src.collectors import (
    catch, jobkorea, jumpit, saramin, wanted, work24, zighang)
from src.cleanup import cleanup_expired
from src.dashboard import render_dashboard
from src.enrich import enrich
from src.history import HistoryStore
from src.mailer import render_html, send_email
from src.notion_sync import sync as notion_sync
from src.store import SeenStore

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR_FUNCS = {"wanted": wanted.search, "saramin": saramin.search,
                   "work24": work24.search, "jumpit": jumpit.search,
                   "catch": catch.search, "jobkorea": jobkorea.search,
                   "zighang": zighang.search}


def setup_logging() -> logging.Logger:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "job_scout.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return logging.getLogger("job_scout")


def build_collectors(pcfg: dict, log: logging.Logger) -> dict:
    """사람 설정의 sites/필터로 수집기 dict를 만든다."""
    max_exp = pcfg.get("max_experience_from", 1)
    collectors = {}
    for site, enabled in pcfg.get("sites", {}).items():
        if not enabled:
            continue
        if site not in COLLECTOR_FUNCS:
            log.warning("%s 사이트가 활성화되어 있지만 수집기가 없습니다 — 건너뜀", site)
            continue
        func = COLLECTOR_FUNCS[site]
        if site in ("wanted", "jumpit", "zighang"):
            func = functools.partial(func, max_experience_from=max_exp)
        if site == "jumpit":
            func = functools.partial(
                func, categories=pcfg.get("jumpit_categories", jumpit.DEFAULT_CATEGORIES))
        # 사람별 직무 카테고리 코드 (비IT 직군 대응)
        if site == "zighang" and pcfg.get("zighang_categories"):
            func = functools.partial(func, categories=pcfg["zighang_categories"])
        if site == "catch" and pcfg.get("catch_jobcode"):
            func = functools.partial(func, params={"JobCode": pcfg["catch_jobcode"]})
        if site == "work24" and pcfg.get("work24_dty"):
            func = functools.partial(func, dty=pcfg["work24_dty"])
        collectors[site] = func
    return collectors


def run_enrich(token: str, db: str, profile: str, pcfg: dict,
               log: logging.Logger) -> None:
    """노션의 수동 입력 링크(점수 빈 row)를 채점해 채운다. 실패해도 본 흐름은 계속."""
    try:
        ok, fail = asyncio.run(enrich(token, db, profile, pcfg))
        if ok or fail:
            log.info("[%s] 수동 링크 보강: 성공 %d건, 실패 %d건",
                     pcfg["id"], ok, fail)
    except Exception:
        log.exception("[%s] 수동 링크 보강 실패 — 계속 진행", pcfg["id"])


def run_cleanup(token: str, db: str, pid: str, log: logging.Logger) -> None:
    """마감일이 지난 노션 공고를 아카이브한다. 실패해도 본 흐름은 계속."""
    try:
        n = cleanup_expired(token, db)
        if n:
            log.info("[%s] 마감 지난 공고 정리: %d건 아카이브", pid, n)
    except Exception:
        log.exception("[%s] 마감 공고 정리 실패 — 계속 진행", pid)


def run_person(pcfg: dict, args, log: logging.Logger) -> None:
    """한 사람에 대해 보강·정리·수집·채점·저장·발송을 수행한다."""
    pid = pcfg["id"]
    token = os.environ.get("NOTION_TOKEN", "").strip()
    db = os.environ.get(pcfg.get("notion_db_env", ""), "").strip()
    profile = (ROOT / pcfg["profile"]).read_text(encoding="utf-8")
    data_dir = ROOT / "data" / pid
    data_dir.mkdir(parents=True, exist_ok=True)

    # 수동 링크 보강 + 마감 정리 (Notion 자격증명 있을 때만)
    if not args.dry_run and token and db:
        run_enrich(token, db, profile, pcfg, log)
        run_cleanup(token, db, pid, log)
    if args.enrich_only:
        return

    store = SeenStore(data_dir / "seen.json")
    collectors = build_collectors(pcfg, log)
    log.info("[%s] 수집 시작 (사이트: %s)", pid, list(collectors))
    scored, fetched_ids, failures, postings_by_id = asyncio.run(
        run_agent(pcfg, profile, collectors, store))
    for f in failures:
        log.warning("[%s] %s", pid, f)
    picked = sorted([s for s in scored if s.score >= pcfg["min_score"]],
                    key=lambda s: s.score, reverse=True)[: pcfg["top_n"]]
    log.info("[%s] 신규 %d건, 채점 %d건, 발송 대상 %d건",
             pid, len(fetched_ids), len(scored), len(picked))

    today = datetime.date.today().isoformat()
    if not args.dry_run and scored:
        history = HistoryStore(data_dir / "history.json")
        new_entries = history.add(scored, today, postings_by_id)
        dashboard_path = ROOT / "reports" / pid / "dashboard.html"
        dashboard_path.parent.mkdir(parents=True, exist_ok=True)
        dashboard_path.write_text(render_dashboard(history.entries), encoding="utf-8")
        log.info("[%s] 대시보드 갱신 (누적 반영 신규 %d건)", pid, len(new_entries))

        notion_min = pcfg.get("notion_min_score", 5)
        # 이미 마감된(마감일 < 오늘) 공고는 애초에 올리지 않는다.
        notion_entries = [e for e in new_entries if e["score"] >= notion_min
                          and not (e.get("deadline") and e["deadline"] < today)]
        if token and db and notion_entries:
            try:
                created = notion_sync(notion_entries, token, db)
                log.info("[%s] Notion 동기화 완료: %d건 (%d점 이상, 신규 %d건 중)",
                         pid, created, notion_min, len(new_entries))
            except Exception:
                log.exception("[%s] Notion 동기화 실패 — 계속 진행", pid)

    if args.dry_run:
        print(f"\n===== [{pid}] =====")
        for job in picked:
            print(f"[{job.score}/10] {job.title} — {job.company}\n"
                  f"  {job.url}\n  이유: {job.reason}\n  {job.summary}\n")
        return

    if not picked:
        if scored or not fetched_ids:
            store.mark(fetched_ids)
        else:
            log.warning("[%s] 채점 결과 없음 — seen 기록 생략, 다음 실행에서 재시도", pid)
        log.info("[%s] 발송할 공고 없음", pid)
        return

    email_cfg = pcfg["email"]
    if email_cfg.get("enabled", True):
        subject = f"[job-scout:{pid}] {today} 신규 공고 {len(picked)}건"
        body = render_html(picked, failures)
        try:
            send_email(subject, body, email_cfg)
            log.info("[%s] 이메일 발송 완료: %s", pid, email_cfg["to"])
        except Exception:
            backup = ROOT / "reports" / pid / f"{today}.html"
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(body, encoding="utf-8")
            log.exception("[%s] 이메일 발송 실패 — 백업 저장: %s", pid, backup)
    store.mark(fetched_ids)


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="이메일·저장 없이 콘솔에 출력")
    parser.add_argument("--enrich-only", action="store_true",
                        help="수집·발송 없이 노션의 수동 입력 링크만 채점·보강")
    parser.add_argument("--person", help="특정 사람(id)만 실행")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    log = setup_logging()
    try:
        config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        email_cfg = config.get("email", {"enabled": False})
        defaults = config.get("defaults", {})
        people = config["people"]
        if args.person:
            people = [p for p in people if p["id"] == args.person]
            if not people:
                log.error("사람 id를 찾을 수 없습니다: %s", args.person)
                raise SystemExit(1)

        email_enabled = email_cfg.get("enabled", True)
        if not args.dry_run and not args.enrich_only and email_enabled and (
                not os.environ.get("SMTP_USER") or not os.environ.get("SMTP_PASSWORD")):
            log.error("SMTP 자격증명이 없어 중단 (.env 설정 또는 email.enabled: false)")
            raise SystemExit(1)

        for person in people:
            pcfg = {**defaults, **person, "email": email_cfg}
            try:
                run_person(pcfg, args, log)
            except Exception:
                log.exception("[%s] 실행 실패 — 다음 사람 계속", person.get("id"))
    except SystemExit:
        raise
    except Exception:
        log.exception("실행 실패")
        raise


if __name__ == "__main__":
    main()

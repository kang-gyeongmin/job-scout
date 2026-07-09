"""진입점: 에이전트 실행(툴로 수집 주도) → 결과 이메일 발송."""
import argparse
import asyncio
import datetime
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.agent import run_agent
from src.collectors import wanted
from src.mailer import render_html, send_email
from src.store import SeenStore

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR_FUNCS = {"wanted": wanted.search}
# Task 8/9 완료 시 여기에 saramin/rocketpunch 추가


def setup_logging() -> logging.Logger:
    log_dir = ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "job_scout.log", level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    return logging.getLogger("job_scout")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="이메일을 보내지 않고 콘솔에 출력, seen 기록 안 함")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    log = setup_logging()
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    profile = (ROOT / "profile.md").read_text(encoding="utf-8")
    store = SeenStore(ROOT / "data" / "seen.json")

    collectors = {site: COLLECTOR_FUNCS[site]
                  for site, enabled in config["sites"].items()
                  if enabled and site in COLLECTOR_FUNCS}

    log.info("에이전트 실행 시작 (사이트: %s)", list(collectors))
    scored, fetched_ids, failures = asyncio.run(
        run_agent(config, profile, collectors, store))
    for f in failures:
        log.warning(f)
    picked = sorted([s for s in scored if s.score >= config["min_score"]],
                    key=lambda s: s.score, reverse=True)[: config["top_n"]]
    log.info("신규 %d건, 채점 %d건, 발송 대상 %d건",
             len(fetched_ids), len(scored), len(picked))

    if args.dry_run:
        for job in picked:
            print(f"[{job.score}/10] {job.title} — {job.company}\n"
                  f"  {job.url}\n  이유: {job.reason}\n  {job.summary}\n")
        log.info("dry-run 종료 (발송·기록 없음)")
        return

    if not picked:
        store.mark(fetched_ids)  # 저점 공고도 재알림 방지
        log.info("발송할 공고 없음")
        return

    today = datetime.date.today().isoformat()
    subject = f"[job-scout] {today} 신규 공고 {len(picked)}건"
    body = render_html(picked, failures)
    try:
        send_email(subject, body, config["email"])
        log.info("이메일 발송 완료: %s", config["email"]["to"])
    except Exception:
        backup = ROOT / "reports" / f"{today}.html"
        backup.parent.mkdir(exist_ok=True)
        backup.write_text(body, encoding="utf-8")
        log.exception("이메일 발송 실패 — 백업 저장: %s", backup)
        raise
    store.mark(fetched_ids)


if __name__ == "__main__":
    main()

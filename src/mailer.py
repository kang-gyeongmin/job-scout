"""HTML 이메일 렌더링 및 네이버 SMTP 발송."""
import html
import os
import smtplib
from email.mime.text import MIMEText

from src.agent import ScoredJob

SITE_LABEL = {"wanted": "원티드", "saramin": "사람인", "rocketpunch": "로켓펀치"}


def render_html(scored: list[ScoredJob], failures: list[str]) -> str:
    rows = []
    for job in sorted(scored, key=lambda j: j.score, reverse=True):
        rows.append(f"""
        <div style="border:1px solid #ddd;border-radius:8px;padding:12px;margin:10px 0">
          <div style="font-size:13px;color:#888">{html.escape(SITE_LABEL.get(job.site, job.site))}
            &nbsp;|&nbsp; 적합도 <b>{job.score}/10</b></div>
          <div style="font-size:16px;margin:4px 0">
            <a href="{html.escape(job.url)}"><b>{html.escape(job.title)}</b></a>
            — {html.escape(job.company)}</div>
          <div style="font-size:13px;color:#444">이유: {html.escape(job.reason)}</div>
          <div style="font-size:13px;color:#444;white-space:pre-line">{html.escape(job.summary)}</div>
        </div>""")
    failure_html = ""
    if failures:
        items = "".join(f"<li>{html.escape(f)}</li>" for f in failures)
        failure_html = f'<hr><div style="color:#a00;font-size:12px"><ul>{items}</ul></div>'
    return f"<html><body>{''.join(rows)}{failure_html}</body></html>"


def send_email(subject: str, body_html: str, cfg: dict) -> None:
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)

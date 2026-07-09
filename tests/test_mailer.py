from unittest.mock import MagicMock, patch

from src.agent import ScoredJob
from src.mailer import render_html, send_email


def make_job(score: int, title: str) -> ScoredJob:
    return ScoredJob(id=f"wanted:{score}", site="wanted", title=title,
                     company="회사", url=f"https://x/{score}", score=score,
                     reason="스택 일치", summary="파이프라인 구축 포지션")


def test_render_html_sorted_by_score_desc_with_links():
    html = render_html([make_job(6, "낮은거"), make_job(9, "높은거")], [])
    assert html.index("높은거") < html.index("낮은거")
    assert 'href="https://x/9"' in html


def test_render_html_shows_failures():
    html = render_html([make_job(7, "공고")], ["saramin 수집 실패"])
    assert "saramin 수집 실패" in html


def test_render_html_escapes_unknown_site_label():
    job = ScoredJob(id="x:1", site="<b>x</b>", title="공고", company="회사",
                    url="https://x/1", score=5, reason="이유", summary="요약")
    html = render_html([job], [])
    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html


def test_send_email_sets_date_and_message_id_headers_and_logs_in(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "user@naver.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    cfg = {"from": "user@naver.com", "to": "target@example.com",
          "smtp_host": "smtp.naver.com", "smtp_port": 465}

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    with patch("smtplib.SMTP_SSL", return_value=mock_smtp) as mock_ctor:
        send_email("제목", "<html></html>", cfg)

    mock_ctor.assert_called_once_with("smtp.naver.com", 465, timeout=30)
    mock_smtp.login.assert_called_once_with("user@naver.com", "secret")
    assert mock_smtp.send_message.called
    sent_msg = mock_smtp.send_message.call_args[0][0]
    assert sent_msg["Date"]
    assert sent_msg["Message-ID"]

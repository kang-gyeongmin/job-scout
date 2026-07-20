"""누적 채점 결과를 보는 정적 HTML 대시보드 생성기.

reports/dashboard.html 하나로 완결된다 — 서버·외부 리소스 없이 브라우저로
열면 되고, 데이터는 파일 안에 JSON으로 내장된다. 검색·필터·정렬은
클라이언트 JS로 처리하며, 공고별 지원 상태(관심/지원함/제외)는 브라우저
localStorage에 저장되므로 파일이 매일 재생성돼도 유지된다.
"""
import json

from src.mailer import SITE_LABEL

STATUSES = ["신규", "관심", "지원함", "제외"]


def render_dashboard(entries: list[dict]) -> str:
    # "</script>" 조기 종료 방지를 위해 </ 를 이스케이프해 내장한다
    data = json.dumps(entries, ensure_ascii=False).replace("</", "<\\/")
    site_labels = json.dumps(SITE_LABEL, ensure_ascii=False)
    statuses = json.dumps(STATUSES, ensure_ascii=False)
    return """<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>job-scout 대시보드</title>
<style>
  :root { color-scheme: light dark;
    --bg:#f6f7f9; --card:#fff; --text:#1c1e21; --muted:#65707d;
    --line:#e1e4e8; --accent:#2563eb; }
  @media (prefers-color-scheme: dark) { :root {
    --bg:#16181c; --card:#1f2228; --text:#e8eaed; --muted:#9aa4b1;
    --line:#33373e; --accent:#7aa2ff; } }
  * { box-sizing:border-box }
  body { margin:0; background:var(--bg); color:var(--text);
    font:15px/1.5 -apple-system,"Malgun Gothic","Apple SD Gothic Neo",sans-serif }
  header { padding:20px 16px 0; max-width:860px; margin:0 auto }
  h1 { font-size:20px; margin:0 0 4px } .sub { color:var(--muted); font-size:13px }
  #controls { display:flex; flex-wrap:wrap; gap:8px; max-width:860px;
    margin:14px auto 0; padding:0 16px }
  #controls input, #controls select { padding:7px 10px; border:1px solid var(--line);
    border-radius:8px; background:var(--card); color:var(--text); font-size:14px }
  #q { flex:1; min-width:160px }
  main { max-width:860px; margin:12px auto 40px; padding:0 16px }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:14px 16px; margin:10px 0 }
  .card.done { opacity:.55 }
  .meta { font-size:12px; color:var(--muted); display:flex; gap:8px; flex-wrap:wrap;
    align-items:center }
  .score { font-weight:700; color:var(--accent) }
  .title { font-size:16px; margin:4px 0 }
  .title a { color:var(--text); text-decoration:none }
  .title a:hover { text-decoration:underline }
  .reason { font-size:13px; color:var(--muted) }
  .summary { font-size:13px; margin-top:6px; white-space:pre-line }
  .statuses { margin-top:10px; display:flex; gap:6px }
  .statuses button { padding:4px 10px; font-size:12px; border-radius:999px;
    border:1px solid var(--line); background:transparent; color:var(--muted);
    cursor:pointer }
  .statuses button.on { background:var(--accent); border-color:var(--accent);
    color:#fff }
  #empty { text-align:center; color:var(--muted); padding:40px 0 }
</style>
<header>
  <h1>job-scout 대시보드</h1>
  <div class="sub" id="stats"></div>
</header>
<div id="controls">
  <input id="q" type="search" placeholder="제목·회사 검색">
  <select id="site"><option value="">모든 사이트</option></select>
  <select id="minScore"></select>
  <select id="status"><option value="">모든 상태</option></select>
  <select id="sort">
    <option value="date">최신순</option>
    <option value="score">점수순</option>
  </select>
</div>
<main><div id="list"></div><div id="empty" hidden>조건에 맞는 공고가 없습니다</div></main>
<script>
const JOBS = __DATA__;
const SITE_LABEL = __SITE_LABELS__;
const STATUSES = __STATUSES__;
const LS_KEY = "job-scout-status";
const saved = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
const statusOf = j => saved[j.id] || "신규";
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const $ = id => document.getElementById(id);
for (const s of [...new Set(JOBS.map(j => j.site))])
  $("site").insertAdjacentHTML("beforeend",
    `<option value="${esc(s)}">${esc(SITE_LABEL[s] || s)}</option>`);
for (let n = 0; n <= 10; n++)
  $("minScore").insertAdjacentHTML("beforeend",
    `<option value="${n}" ${n === 6 ? "selected" : ""}>${n}점 이상</option>`);
for (const s of STATUSES)
  $("status").insertAdjacentHTML("beforeend",
    `<option value="${esc(s)}">${esc(s)}</option>`);

function render() {
  const q = $("q").value.trim().toLowerCase();
  const rows = JOBS.filter(j =>
    (!$("site").value || j.site === $("site").value) &&
    j.score >= +$("minScore").value &&
    (!$("status").value || statusOf(j) === $("status").value) &&
    (!q || (j.title + j.company).toLowerCase().includes(q)));
  rows.sort((a, b) => $("sort").value === "score"
    ? b.score - a.score || b.date.localeCompare(a.date)
    : b.date.localeCompare(a.date) || b.score - a.score);

  $("stats").textContent = `전체 ${JOBS.length}건 · 표시 ${rows.length}건 · ` +
    `지원함 ${JOBS.filter(j => statusOf(j) === "지원함").length}건`;
  $("empty").hidden = rows.length > 0;
  $("list").innerHTML = rows.map(j => {
    const st = statusOf(j);
    return `<div class="card ${st === "제외" ? "done" : ""}">
      <div class="meta"><span>${esc(SITE_LABEL[j.site] || j.site)}</span>
        <span class="score">${j.score}/10</span><span>${esc(j.date)}</span>
        ${j.deadline ? `<span>마감 ${esc(j.deadline)}</span>` : ""}</div>
      <div class="title"><a href="${esc(j.url)}" target="_blank" rel="noopener">
        ${esc(j.title)}</a> — ${esc(j.company)}</div>
      <div class="reason">${esc(j.reason)}</div>
      <div class="summary">${esc(j.summary)}</div>
      <div class="statuses">${STATUSES.map(s =>
        `<button data-id="${esc(j.id)}" data-s="${esc(s)}"
           class="${s === st ? "on" : ""}">${esc(s)}</button>`).join("")}</div>
    </div>`;
  }).join("");
}

$("list").addEventListener("click", e => {
  const b = e.target.closest("button[data-id]");
  if (!b) return;
  saved[b.dataset.id] = b.dataset.s;
  localStorage.setItem(LS_KEY, JSON.stringify(saved));
  render();
});
for (const id of ["q", "site", "minScore", "status", "sort"])
  $(id).addEventListener("input", render);
render();
</script>
</html>
""".replace("__DATA__", data) \
   .replace("__SITE_LABELS__", site_labels) \
   .replace("__STATUSES__", statuses)

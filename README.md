# job-scout

원티드·사람인·로켓펀치에서 조건에 맞는 채용 공고를 매일 수집해,
Claude 에이전트가 프로필 대비 적합도를 채점·요약하고 이메일로 보내주는 봇.

## 실행

```powershell
uv run python -m src.main --dry-run   # 콘솔 출력만 (기록·발송·동기화 없음)
uv run python -m src.main             # 수집·채점 → 대시보드·Notion 갱신 (+이메일)
```

이메일 발송은 `config.yaml`의 `email.enabled`로 켜고 끈다 (현재 기본 꺼짐 —
Notion·대시보드만 갱신).

설정은 `config.yaml`, 판단 기준 프로필은 `profile.md`, 비밀값은 `.env`(예시: `.env.example`).

## 매일 자동 실행

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Time "09:00"
```

- 실행 기록: `logs\job_scout.log`
- 발송 실패 백업: `reports\YYYY-MM-DD.html`
- 중복 방지 기록 초기화: `data\seen.json` 삭제
- 해제: `schtasks /Delete /TN job-scout-daily /F`

## 대시보드

매 실행마다 채점 결과가 `data\history.json`에 누적되고,
`reports\dashboard.html`이 갱신된다. 브라우저로 열면 검색·사이트·점수·상태
필터와 정렬을 쓸 수 있고, 공고별 지원 상태(신규/관심/지원함/제외)는
브라우저(localStorage)에 저장되어 파일이 재생성돼도 유지된다.

## Notion 연동 (선택)

채점된 공고를 매일 Notion 데이터베이스에도 쌓을 수 있다.

1. https://www.notion.so/my-integrations 에서 통합 생성 → 시크릿을 `.env`의
   `NOTION_TOKEN`에 저장
2. DB를 둘 페이지에 통합을 연결하고, 페이지 ID를 `NOTION_PARENT_PAGE_ID`에 저장
3. `uv run python scripts/setup_notion.py` 실행 → 출력된 `NOTION_DB_ID`를
   `.env`에 추가

이후 실행부터 새 공고가 자동으로 DB에 추가된다 (상태 컬럼으로 지원 관리 가능).
`NOTION_TOKEN`/`NOTION_DB_ID`가 없으면 조용히 건너뛴다.

## 사이트 추가 상태

| 사이트 | 상태 | 비고 |
|---|---|---|
| 원티드 | ✅ | 내부 JSON API, 서울·경기·인천 |
| 청년일경험(Work24) | ✅ | IT 직무·수도권/지역무관 고정 필터, 인턴형·프로젝트형·ESG (기업탐방형 제외). 상세가 POST 전용이라 링크는 목록 페이지로 연결 |
| 사람인 | ✅ 코드 완료 | `.env`에 API 키 넣고 `config.yaml`에서 `saramin: true` |
| 로켓펀치 | ⏳ | 클라이언트 렌더링 + AWS WAF 챌린지로 보류 |

# job-scout

원티드·사람인·로켓펀치에서 조건에 맞는 채용 공고를 매일 수집해,
Claude 에이전트가 프로필 대비 적합도를 채점·요약하고 이메일로 보내주는 봇.

## 실행

```powershell
uv run python -m src.main --dry-run   # 이메일 없이 콘솔 출력
uv run python -m src.main             # 실제 이메일 발송
```

설정은 `config.yaml`, 판단 기준 프로필은 `profile.md`, 비밀값은 `.env`(예시: `.env.example`).

## 매일 자동 실행

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 -Time "09:00"
```

- 실행 기록: `logs\job_scout.log`
- 발송 실패 백업: `reports\YYYY-MM-DD.html`
- 중복 방지 기록 초기화: `data\seen.json` 삭제
- 해제: `schtasks /Delete /TN job-scout-daily /F`

## 사이트 추가 상태

| 사이트 | 상태 | 비고 |
|---|---|---|
| 원티드 | ✅ | 내부 JSON API |
| 사람인 | ⏳ | 오픈 API 키 발급 후 `config.yaml`에서 활성화 |
| 로켓펀치 | ⏳ | HTML 크롤링 |

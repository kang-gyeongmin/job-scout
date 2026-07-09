# job-scout

원티드·사람인·로켓펀치에서 조건에 맞는 채용 공고를 매일 수집해,
Claude 에이전트가 프로필 대비 적합도를 채점·요약하고 이메일로 보내주는 봇.

## 실행

```powershell
uv run python -m src.main --dry-run   # 이메일 없이 콘솔 출력
uv run python -m src.main             # 실제 이메일 발송
```

설정은 `config.yaml`, 판단 기준 프로필은 `profile.md`, 비밀값은 `.env`(예시: `.env.example`).

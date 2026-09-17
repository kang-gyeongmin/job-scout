#!/bin/zsh
# launchd가 매일 실행하는 래퍼 — 등록은 scripts/register_launchd.sh 참고.
# launchd는 셸 프로필을 읽지 않으므로 uv·claude(nvm) 경로를 직접 지정한다.
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v18.20.4/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd "$(dirname "$0")/.." || exit 1

# 맥이 막 깨어난 직후엔 네트워크(DNS)가 아직 안 붙어 있을 수 있다.
# 인터넷이 준비될 때까지 최대 5분(10초 x 30회) 기다린 뒤 실행한다.
for i in $(seq 1 30); do
  if curl -sf --max-time 5 https://api.notion.com/v1 >/dev/null 2>&1 \
     || ping -c1 -t3 api.notion.com >/dev/null 2>&1; then
    break
  fi
  sleep 10
done

# caffeinate -i: 실행 도중 유휴 슬립을 막아(맥이 sleep=1분 정책이라도) 끝까지 돌게 한다.
exec caffeinate -i uv run python -m src.main

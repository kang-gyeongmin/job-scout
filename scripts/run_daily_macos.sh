#!/bin/zsh
# launchd가 매일 실행하는 래퍼 — 등록은 scripts/register_launchd.sh 참고.
# launchd는 셸 프로필을 읽지 않으므로 uv·claude(nvm) 경로를 직접 지정한다.
export PATH="$HOME/.local/bin:$HOME/.nvm/versions/node/v18.20.4/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

cd "$(dirname "$0")/.." || exit 1
exec uv run python -m src.main

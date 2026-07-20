#!/bin/zsh
# macOS 매일 자동 실행 등록 (기본 09:00). Windows는 register_task.ps1 사용.
#   ./scripts/register_launchd.sh          # 09:00 등록
#   ./scripts/register_launchd.sh 8 30     # 08:30 등록
# 해제: launchctl bootout gui/$(id -u)/com.job-scout.daily
set -e
HOUR="${1:-9}"
MINUTE="${2:-0}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.job-scout.daily.plist"

mkdir -p "$REPO/logs" "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.job-scout.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>$REPO/scripts/run_daily_macos.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key><string>$REPO/logs/launchd.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/com.job-scout.daily" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "등록 완료: 매일 $(printf '%02d:%02d' "$HOUR" "$MINUTE") 실행 (com.job-scout.daily)"

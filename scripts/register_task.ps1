# job-scout를 매일 09:00에 실행하는 Windows 예약 작업을 등록한다.
# 사용법: powershell -ExecutionPolicy Bypass -File scripts\register_task.ps1 [-Time "09:00"]
param([string]$Time = "09:00")

$repo = Split-Path -Parent $PSScriptRoot
$uv = (Get-Command uv).Source
$action = "`"$uv`" run --directory `"$repo`" python -m src.main"

schtasks /Create /F /TN "job-scout-daily" /SC DAILY /ST $Time /TR $action
Write-Host "등록 완료. 확인: schtasks /Query /TN job-scout-daily"
Write-Host "즉시 테스트: schtasks /Run /TN job-scout-daily (이후 logs\job_scout.log 확인)"

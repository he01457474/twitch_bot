$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$startScript = Join-Path $ProjectRoot 'scripts\start_secretary.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$startScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName 'SecretaryBotAutoStart' -Action $action -Trigger $trigger -RunLevel Limited -Force | Out-Null

Write-Host ''
Write-Host '已設定：開機登入時會自動啟動私人秘書 Bot。' -ForegroundColor Green
Read-Host '按 Enter 關閉'

Unregister-ScheduledTask -TaskName 'SecretaryBotAutoStart' -Confirm:$false -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '已取消開機自動啟動。' -ForegroundColor Green
Read-Host '按 Enter 關閉'

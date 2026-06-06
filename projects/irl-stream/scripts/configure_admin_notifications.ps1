$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir = Get-IrlConfigDir
$ConfigPath = Join-Path $ConfigDir 'notification.json'
$NotifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'

function Read-Required {
    param([string]$Prompt)
    do {
        $value = Read-Host $Prompt
        $value = if ($null -eq $value) { '' } else { $value.Trim() }
        if (-not $value) { Write-Host '這個欄位不能空白。' -ForegroundColor Red }
    } while (-not $value)
    return $value
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '      設定管理員通知         ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '目前只支援 Discord Webhook。通知只傳給管理員，不傳給台主本人。' -ForegroundColor Yellow
Write-Host ''

$webhookUrl = Read-Required 'Discord Webhook URL'
$cooldownRaw = Read-Host '同類通知冷卻分鐘數（Enter 使用 5）'
$cooldownRaw = if ($null -eq $cooldownRaw) { '' } else { $cooldownRaw.Trim() }
$cooldown = 5
if ($cooldownRaw) {
    [int]::TryParse($cooldownRaw, [ref]$cooldown) | Out-Null
    if ($cooldown -lt 0) { $cooldown = 5 }
}

New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
$config = [pscustomobject]@{
    enabled = $true
    provider = 'Discord'
    discordWebhookUrl = $webhookUrl
    cooldownMinutes = $cooldown
    notifyAdminOnly = $true
    updatedAt = (Get-Date).ToString('o')
}
$json = $config | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($ConfigPath, $json, [System.Text.UTF8Encoding]::new($false))

Write-Host ''
Write-Host "通知設定已儲存：$ConfigPath" -ForegroundColor Green
Write-Host '正在送出測試通知...' -ForegroundColor Cyan
& $NotifyScript -Title 'IRL 管理員通知測試' -Message 'Discord Webhook 已設定完成。' -Level Success -Key 'notification-test' -CooldownMinutes 0
Write-Host '如果 Discord 有收到測試訊息，代表設定成功。' -ForegroundColor Green
Read-Host '按 Enter 關閉'

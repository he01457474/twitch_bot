param(
    [string]$PidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')
$stopFlag = Get-IrlStopFlagPath

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII
$updateScript = Join-Path $PSScriptRoot 'update_dynu_ddns.ps1'
$notifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'
$intervalSeconds = 900

function Send-AdminNotification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Level = 'Info',
        [string]$Key = '',
        [int]$CooldownMinutes = 5
    )

    if (Test-Path $notifyScript) {
        & $notifyScript -Title $Title -Message $Message -Level $Level -Key $Key -CooldownMinutes $CooldownMinutes
    }
}

$failureNotified = $false
$lastFailureMessage = ''

function Test-DynuErrorShouldNotify {
    param([string]$Message)

    if (-not $Message) { return $false }
    if ($Message -match 'badauth|notfqdn|nohost|badagent|911|Dynu 設定不完整|密碼格式已過期') { return $true }
    return $false
}

while ($true) {
    if (Test-Path -LiteralPath $stopFlag) { exit }
    try {
        & $updateScript | Out-Null
        if ($failureNotified) {
            $message = 'Dynu DDNS 背景更新已恢復成功。'
            if ($lastFailureMessage) {
                $message += "`n前一次錯誤：$lastFailureMessage"
            }
            Send-AdminNotification -Title 'Dynu DDNS 背景更新已恢復' -Message $message -Level Success -Key 'dynu-watchdog-recovered' -CooldownMinutes 0
            $failureNotified = $false
            $lastFailureMessage = ''
        }
    } catch {
        # Keep retrying while the IRL environment is open.
        $lastFailureMessage = $_.Exception.Message
        if (Test-DynuErrorShouldNotify $lastFailureMessage) {
            Send-AdminNotification -Title 'Dynu DDNS 設定或服務異常' -Message $lastFailureMessage -Level Error -Key 'dynu-watchdog-failed' -CooldownMinutes 60
            $failureNotified = $true
        }
    }
    Start-Sleep -Seconds $intervalSeconds
}

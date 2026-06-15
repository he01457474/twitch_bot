param(
    [string]$PidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')
$stopFlag = Get-IrlStopFlagPath

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII
$updateScript = Join-Path $PSScriptRoot 'update_dynu_ddns.ps1'
$notifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'

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

while ($true) {
    if (Test-Path -LiteralPath $stopFlag) { exit }
    try {
        & $updateScript | Out-Null
    } catch {
        # Keep retrying while the IRL environment is open.
        Send-AdminNotification -Title 'Dynu DDNS 背景更新失敗' -Message $_.Exception.Message -Level Error -Key 'dynu-watchdog-failed' -CooldownMinutes 10
    }
    Start-Sleep -Seconds 300
}

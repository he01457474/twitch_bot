param(
    [string]$PidFile = "$env:TEMP\irl_network_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')
$stopFlag = Get-IrlStopFlagPath

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII
$notifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'
$checkIntervalSeconds = 20
$downNotifyAfterSeconds = 60
$probeUrls = @(
    'https://discord.com',
    'https://api.ipify.org',
    'https://api.dynu.com'
)

function Send-AdminNotification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Level = 'Info',
        [string]$Key = '',
        [int]$CooldownMinutes = 1
    )

    if (Test-Path -LiteralPath $notifyScript) {
        & $notifyScript -Title $Title -Message $Message -Level $Level -Key $Key -CooldownMinutes $CooldownMinutes
    }
}

function Test-InternetConnection {
    foreach ($url in $probeUrls) {
        try {
            Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 | Out-Null
            return $true
        } catch {}
    }
    return $false
}

$wasUp = $true
$downSince = $null
$downNotified = $false

while ($true) {
    Start-Sleep -Seconds $checkIntervalSeconds
    if (Test-Path -LiteralPath $stopFlag) { exit }

    $isUp = Test-InternetConnection
    $ts = Get-Date -Format 'HH:mm:ss'

    if (-not $isUp -and $wasUp) {
        $downSince = Get-Date
        Write-Host "[$ts] 偵測到網路斷線" -ForegroundColor Yellow
    }

    if (-not $isUp -and -not $downNotified -and $downSince) {
        $span = (Get-Date) - $downSince
        if ($span.TotalSeconds -ge $downNotifyAfterSeconds) {
            $durationMsg = "已持續約 {0} 分 {1} 秒。" -f [int]$span.TotalMinutes, $span.Seconds
            Send-AdminNotification -Title 'IRL 網路可能已斷線' -Message "筆電目前無法連到外網。$durationMsg`n借用台主可能無法推流或會中斷。" -Level Error -Key 'network-down' -CooldownMinutes 5
            $downNotified = $true
        }
    }

    if ($isUp -and -not $wasUp) {
        $durationMsg = ''
        if ($downSince) {
            $span = (Get-Date) - $downSince
            $durationMsg = "斷線時長約 {0} 分 {1} 秒。" -f [int]$span.TotalMinutes, $span.Seconds
        }
        Write-Host "[$ts] 網路已恢復連線" -ForegroundColor Green
        if ($downNotified) {
            Send-AdminNotification -Title 'IRL 網路已恢復連線' -Message "筆電外網連線已恢復。$durationMsg" -Level Success -Key 'network-recovered' -CooldownMinutes 1
        }
        $downSince = $null
        $downNotified = $false
    }

    $wasUp = $isUp
}

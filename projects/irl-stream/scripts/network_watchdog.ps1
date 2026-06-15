param(
    [string]$PidFile = "$env:TEMP\irl_network_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')
$stopFlag = Get-IrlStopFlagPath

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII
$notifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'

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
    try {
        Invoke-WebRequest -Uri 'https://discord.com' -UseBasicParsing -TimeoutSec 5 | Out-Null
        return $true
    } catch {
        return $false
    }
}

$wasUp = $true
$downSince = $null

while ($true) {
    Start-Sleep -Seconds 20
    if (Test-Path -LiteralPath $stopFlag) { exit }

    $isUp = Test-InternetConnection
    $ts = Get-Date -Format 'HH:mm:ss'

    if (-not $isUp -and $wasUp) {
        $downSince = Get-Date
        Write-Host "[$ts] 偵測到網路斷線" -ForegroundColor Yellow
    } elseif ($isUp -and -not $wasUp) {
        $durationMsg = ''
        if ($downSince) {
            $span = (Get-Date) - $downSince
            $durationMsg = "斷線時長約 {0} 分 {1} 秒。" -f [int]$span.TotalMinutes, $span.Seconds
        }
        Write-Host "[$ts] 網路已恢復連線" -ForegroundColor Green
        Send-AdminNotification -Title '網路已恢復連線' -Message "本機網路連線已恢復。$durationMsg" -Level Success -Key 'network-recovered' -CooldownMinutes 1
        $downSince = $null
    }

    $wasUp = $isUp
}

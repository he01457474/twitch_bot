param(
    [string]$ExePath,
    [string]$ConfigPath,
    [string]$WorkDir,
    [string]$PidFile
)

# 寫入自己的 PID 讓 stream_stop 能終止這個監控程序
[System.IO.File]::WriteAllText($PidFile, [System.Diagnostics.Process]::GetCurrentProcess().Id.ToString())

. (Join-Path $PSScriptRoot 'irl_settings.ps1')
$stopFlag = Get-IrlStopFlagPath

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
    Start-Sleep -Seconds 30
    if (Test-Path -LiteralPath $stopFlag) { exit }
    $proc = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
    if (-not $proc) {
        $ts = Get-Date -Format 'HH:mm:ss'
        Write-Host "[$ts] MediaMTX 已停止，正在重啟..." -ForegroundColor Yellow
        Send-AdminNotification -Title 'MediaMTX 已停止' -Message '監控程式偵測到 MediaMTX 不在執行，正在嘗試自動重啟。' -Level Warning -Key 'mediamtx-stopped' -CooldownMinutes 5
        try {
            Start-Process -FilePath $ExePath -ArgumentList "`"$ConfigPath`"" -WorkingDirectory $WorkDir -WindowStyle Hidden
            Start-Sleep -Seconds 2
            $check = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
            if ($check) {
                Write-Host "[$ts] MediaMTX 重啟成功" -ForegroundColor Green
                Send-AdminNotification -Title 'MediaMTX 重啟成功' -Message 'MediaMTX 已由監控程式自動拉起。' -Level Success -Key 'mediamtx-restarted' -CooldownMinutes 5
            } else {
                Write-Host "[$ts] MediaMTX 重啟失敗，下次再試" -ForegroundColor Red
                Send-AdminNotification -Title 'MediaMTX 重啟失敗' -Message '監控程式已嘗試重啟，但目前仍找不到 mediamtx.exe。' -Level Error -Key 'mediamtx-restart-failed' -CooldownMinutes 5
            }
        } catch {
            Write-Host "[$ts] 重啟時發生錯誤：$_" -ForegroundColor Red
            Send-AdminNotification -Title 'MediaMTX 重啟錯誤' -Message ([string]$_) -Level Error -Key 'mediamtx-restart-error' -CooldownMinutes 5
        }
    }
}

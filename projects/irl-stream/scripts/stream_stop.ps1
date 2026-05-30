Write-Host ''
Write-Host '關閉 IRL 中繼伺服器環境...' -ForegroundColor Cyan
Write-Host ''

# MediaMTX watchdog：先讀 PID，不急著刪檔，後面提權時還需要
$watchdogPidFile = "$env:TEMP\mediamtx_watchdog.pid"
$savedWatchdogPid = $null
if (Test-Path $watchdogPidFile) {
    $rawWdPid = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
    if ($rawWdPid -and $rawWdPid -match '^\d+$') {
        $savedWatchdogPid = [int]$rawWdPid
        Stop-Process -Id $savedWatchdogPid -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $watchdogPidFile -ErrorAction SilentlyContinue
    Write-Host 'MediaMTX 監控已關閉' -ForegroundColor Green
} else {
    Write-Host 'MediaMTX 監控未在執行' -ForegroundColor DarkGray
}

# Dynu DDNS watchdog
$dynuWatchdogPidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
if (Test-Path $dynuWatchdogPidFile) {
    $dPid = Get-Content $dynuWatchdogPidFile -ErrorAction SilentlyContinue
    if ($dPid) { Stop-Process -Id ([int]$dPid) -Force -ErrorAction SilentlyContinue }
    Remove-Item $dynuWatchdogPidFile -ErrorAction SilentlyContinue
    Write-Host 'Dynu DDNS 監控已關閉' -ForegroundColor Green
} else {
    Write-Host 'Dynu DDNS 監控未在執行' -ForegroundColor DarkGray
}

# MediaMTX
$mediamtx = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
if ($mediamtx) {
    try {
        Stop-Process -Name 'mediamtx' -Force -ErrorAction Stop
        Write-Host 'MediaMTX 已關閉' -ForegroundColor Green
    } catch {
        Write-Host '  以管理員身分終止 MediaMTX...' -ForegroundColor Yellow
        # 同時終止可能還活著的 watchdog，避免它重啟 MediaMTX
        $wdCmd = ''
        if ($savedWatchdogPid) {
            $wdCmd = "Stop-Process -Id $savedWatchdogPid -Force -ErrorAction SilentlyContinue; "
        }
        try {
            $killCmd = "${wdCmd}Stop-Process -Name mediamtx -Force -ErrorAction SilentlyContinue"
            $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($killCmd))
            Start-Process powershell -Verb RunAs -WindowStyle Hidden -Wait `
                -ArgumentList "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $enc" `
                -ErrorAction Stop
            Start-Sleep -Milliseconds 800
            if (Get-Process 'mediamtx' -ErrorAction SilentlyContinue) {
                Write-Host '  MediaMTX 仍在執行，請到工作管理員手動結束 mediamtx.exe。' -ForegroundColor Red
            } else {
                Write-Host '  MediaMTX 已關閉' -ForegroundColor Green
            }
        } catch {
            Write-Host '  提權取消，請到工作管理員手動結束 mediamtx.exe。' -ForegroundColor Red
        }
    }
} else {
    Write-Host 'MediaMTX 未在執行' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host 'Dynu DDNS 會在下次啟動直播環境時重新啟動背景更新。' -ForegroundColor DarkGray
Write-Host ''
Write-Host '中繼伺服器環境已關閉完成。' -ForegroundColor Cyan
Start-Sleep -Seconds 3

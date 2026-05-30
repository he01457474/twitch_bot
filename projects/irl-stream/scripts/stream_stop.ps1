# 管理員用：關閉 IRL 中繼伺服器環境

Write-Host "關閉 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，不會關閉借用者電腦上的 NOALBS。" -ForegroundColor DarkGray

# MediaMTX 監控
$watchdogPidFile = "$env:TEMP\mediamtx_watchdog.pid"
if (Test-Path $watchdogPidFile) {
    $wPid = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
    if ($wPid) { Stop-Process -Id ([int]$wPid) -Force -ErrorAction SilentlyContinue }
    Remove-Item $watchdogPidFile -ErrorAction SilentlyContinue
    Write-Host "MediaMTX 監控已關閉" -ForegroundColor Green
} else {
    Write-Host "MediaMTX 監控未在執行" -ForegroundColor DarkGray
}

$dynuWatchdogPidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
if (Test-Path $dynuWatchdogPidFile) {
    $dPid = Get-Content $dynuWatchdogPidFile -ErrorAction SilentlyContinue
    if ($dPid) { Stop-Process -Id ([int]$dPid) -Force -ErrorAction SilentlyContinue }
    Remove-Item $dynuWatchdogPidFile -ErrorAction SilentlyContinue
    Write-Host "Dynu DDNS 監控已關閉" -ForegroundColor Green
}

# MediaMTX 本機版
$mediamtx = Get-Process "mediamtx" -ErrorAction SilentlyContinue
if ($mediamtx) {
    Stop-Process -Name "mediamtx" -Force
    Write-Host "MediaMTX 已關閉" -ForegroundColor Green
} else {
    Write-Host "MediaMTX 未在執行" -ForegroundColor DarkGray
}

Write-Host "Dynu DDNS 會在下次啟動直播環境時重新啟動背景更新。" -ForegroundColor DarkGray

Write-Host ""
Write-Host "中繼伺服器環境已關閉完成。" -ForegroundColor Cyan
Start-Sleep -Seconds 8

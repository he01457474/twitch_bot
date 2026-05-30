[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BrbPidFile = "$env:TEMP\brb_server.pid"

Write-Host ''
Write-Host '關閉桌電直播環境...' -ForegroundColor Cyan
Write-Host ''

# BRB 伺服器
if (Test-Path $BrbPidFile) {
    $savedPid = Get-Content $BrbPidFile -ErrorAction SilentlyContinue
    if ($savedPid) {
        Stop-Process -Id ([int]$savedPid) -Force -ErrorAction SilentlyContinue
        Write-Host 'BRB 伺服器已關閉' -ForegroundColor Green
    }
    Remove-Item $BrbPidFile -ErrorAction SilentlyContinue
} else {
    Write-Host 'BRB 伺服器未在執行' -ForegroundColor DarkGray
}

# NOALBS
if (Get-Process 'noalbs' -ErrorAction SilentlyContinue) {
    Stop-Process -Name 'noalbs' -Force -ErrorAction SilentlyContinue
    Write-Host 'NOALBS 已關閉' -ForegroundColor Green
} else {
    Write-Host 'NOALBS 未在執行' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host '桌電直播環境已關閉。' -ForegroundColor Cyan
Start-Sleep -Seconds 3

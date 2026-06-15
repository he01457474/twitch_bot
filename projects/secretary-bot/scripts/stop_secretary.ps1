$ErrorActionPreference = 'Continue'

$PidFile = "$env:TEMP\secretary_bot.pid"
$WatchdogPidFile = "$env:TEMP\secretary_watchdog.pid"
$StopFlag = "$env:TEMP\secretary_stopping.flag"

Write-Host ''
Write-Host '關閉私人秘書 Bot...' -ForegroundColor Cyan

# 先建立停止旗標並關閉監控程式，避免關閉後被自動重啟
New-Item -ItemType File -Path $StopFlag -Force | Out-Null
if (Test-Path -LiteralPath $WatchdogPidFile) {
    $wdPid = Get-Content -LiteralPath $WatchdogPidFile -ErrorAction SilentlyContinue
    if ($wdPid -and $wdPid -match '^\d+$') {
        Stop-Process -Id ([int]$wdPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $WatchdogPidFile -ErrorAction SilentlyContinue
    Write-Host '監控程式已關閉' -ForegroundColor Green
}

$stopped = $false
if (Test-Path -LiteralPath $PidFile) {
    $targetPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    if ($targetPid -and $targetPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$targetPid) -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id ([int]$targetPid) -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
            $stopped = $true
        }
    }
    Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
}

# 防呆：掃描可能殘留、命令列含 secretary_bot.py 的 pythonw 程序
$strays = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'secretary_bot\.py' }
foreach ($s in $strays) {
    Stop-Process -Id $s.ProcessId -Force -ErrorAction SilentlyContinue
    $stopped = $true
}

if ($stopped) {
    Write-Host '私人秘書 Bot 已關閉' -ForegroundColor Green
} else {
    Write-Host '私人秘書 Bot 目前未在執行' -ForegroundColor DarkGray
}
Start-Sleep -Seconds 2

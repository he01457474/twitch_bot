$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BotScript   = Join-Path $ProjectRoot 'tools\secretary_bot.py'
$PythonExe   = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path '.tools\python-3.13.3-embed\python.exe'
$PidFile     = "$env:TEMP\secretary_bot.pid"
$StopFlag    = "$env:TEMP\secretary_stopping.flag"
$WatchdogScript = Join-Path $PSScriptRoot 'secretary_watchdog.ps1'
$WatchdogPidFile = "$env:TEMP\secretary_watchdog.pid"
$LogDir      = Join-Path $ProjectRoot 'logs'
$StdoutLog   = Join-Path $LogDir 'secretary_stdout.log'
$StderrLog   = Join-Path $LogDir 'secretary_stderr.log'

# 清除上次關閉留下的停止旗標，讓監控程式可以正常運作
Remove-Item -LiteralPath $StopFlag -ErrorAction SilentlyContinue

Write-Host ''
Write-Host '啟動私人秘書 Bot（背景執行）...' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "[錯誤] 找不到 python.exe：$PythonExe" -ForegroundColor Red
    Read-Host '按 Enter 關閉'
    exit 1
}
if (-not (Test-Path -LiteralPath $BotScript)) {
    Write-Host "[錯誤] 找不到主程式：$BotScript" -ForegroundColor Red
    Read-Host '按 Enter 關閉'
    exit 1
}

# 先清掉舊的執行中程序
if (Test-Path -LiteralPath $PidFile) {
    $oldPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    if ($oldPid -and $oldPid -match '^\d+$') {
        Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $PidFile -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Start-Process -FilePath $PythonExe -ArgumentList "`"$BotScript`"" -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog

Start-Sleep -Seconds 2
if (Test-Path -LiteralPath $PidFile) {
    $newPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    Write-Host "私人秘書 Bot 已在背景啟動（PID $newPid）" -ForegroundColor Green
} else {
    Write-Host '私人秘書 Bot 已啟動，正在連線中（稍後可用「關閉私人秘書.bat」結束）' -ForegroundColor Yellow
}
Write-Host '可以直接關掉這個視窗，Bot 會繼續在背景執行。' -ForegroundColor DarkGray

# 啟動監控程式：Bot 斷線重連由 discord.py 自動處理，
# 監控程式負責「整個程序掛掉」時自動重新啟動
if (Test-Path -LiteralPath $WatchdogPidFile) {
    $oldPid = Get-Content -LiteralPath $WatchdogPidFile -ErrorAction SilentlyContinue
    if ($oldPid -and $oldPid -match '^\d+$') {
        Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $WatchdogPidFile -ErrorAction SilentlyContinue
}
Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$WatchdogScript`" -PidFile `"$WatchdogPidFile`"" -WindowStyle Hidden
Write-Host '監控程式已啟動（Bot 程序意外結束時會自動重啟）' -ForegroundColor Green

Start-Sleep -Seconds 2

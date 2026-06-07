$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BotScript   = Join-Path $ProjectRoot 'tools\secretary_bot.py'
$PythonW     = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path '.tools\python-3.13.3-embed\pythonw.exe'
$PidFile     = "$env:TEMP\secretary_bot.pid"

Write-Host ''
Write-Host '啟動私人秘書 Bot（背景執行）...' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $PythonW)) {
    Write-Host "[錯誤] 找不到 pythonw.exe：$PythonW" -ForegroundColor Red
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

Start-Process -FilePath $PythonW -ArgumentList "`"$BotScript`"" -WorkingDirectory $ProjectRoot -WindowStyle Hidden

Start-Sleep -Seconds 2
if (Test-Path -LiteralPath $PidFile) {
    $newPid = Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue
    Write-Host "私人秘書 Bot 已在背景啟動（PID $newPid）" -ForegroundColor Green
} else {
    Write-Host '私人秘書 Bot 已啟動，正在連線中（稍後可用「關閉私人秘書.bat」結束）' -ForegroundColor Yellow
}
Write-Host '可以直接關掉這個視窗，Bot 會繼續在背景執行。' -ForegroundColor DarkGray
Start-Sleep -Seconds 2

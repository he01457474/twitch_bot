param(
    [string]$PidFile = "$env:TEMP\secretary_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BotScript   = Join-Path $ProjectRoot 'tools\secretary_bot.py'
$PythonExe   = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path '.tools\python-3.13.3-embed\python.exe'
$BotPidFile  = "$env:TEMP\secretary_bot.pid"
$StopFlag    = "$env:TEMP\secretary_stopping.flag"
$LogDir      = Join-Path $ProjectRoot 'logs'
$StdoutLog   = Join-Path $LogDir 'secretary_stdout.log'
$StderrLog   = Join-Path $LogDir 'secretary_stderr.log'

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII

while ($true) {
    Start-Sleep -Seconds 60
    if (Test-Path -LiteralPath $StopFlag) { exit }

    $running = $false
    if (Test-Path -LiteralPath $BotPidFile) {
        $botPid = Get-Content -LiteralPath $BotPidFile -ErrorAction SilentlyContinue
        if ($botPid -and $botPid -match '^\d+$') {
            $proc = Get-Process -Id ([int]$botPid) -ErrorAction SilentlyContinue
            if ($proc) { $running = $true }
        }
    }

    if (-not $running) {
        $ts = Get-Date -Format 'HH:mm:ss'
        Write-Host "[$ts] 私人秘書 Bot 未在執行，重新啟動..." -ForegroundColor Yellow
        Remove-Item -LiteralPath $BotPidFile -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        Start-Process -FilePath $PythonExe -ArgumentList "`"$BotScript`"" -WorkingDirectory $ProjectRoot -WindowStyle Hidden -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog
    }
}

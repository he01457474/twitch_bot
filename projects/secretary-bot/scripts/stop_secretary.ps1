$ErrorActionPreference = 'Continue'

$PidFile = "$env:TEMP\secretary_bot.pid"

Write-Host ''
Write-Host '關閉私人秘書 Bot...' -ForegroundColor Cyan

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

@echo off
chcp 65001 > nul

set "PS1URL=https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/install_noalbs_core.ps1"
set "TMPPS1=%TEMP%\install_noalbs_%RANDOM%.ps1"

powershell -ExecutionPolicy Bypass -NoProfile -Command ^
  "Invoke-WebRequest -Uri '%PS1URL%' -OutFile '%TMPPS1%' -UseBasicParsing"

if not exist "%TMPPS1%" (
    echo.
    echo [錯誤] 無法下載安裝腳本，請確認網路連線後重試。
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%TMPPS1%"
del "%TMPPS1%" 2>nul

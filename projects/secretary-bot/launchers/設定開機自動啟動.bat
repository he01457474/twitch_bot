@echo off
set "PROJECT_DIR=%~dp0.."
schtasks /create /tn "SecretaryBotAutoStart" /tr "powershell -ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File \"%PROJECT_DIR%\scripts\start_secretary.ps1\"" /sc onlogon /rl limited /f
echo.
echo 已設定：開機登入時會自動啟動私人秘書 Bot。
pause

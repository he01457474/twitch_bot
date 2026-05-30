@echo off
chcp 65001 >nul
title Force Stop FlyCat Bot

set "SCRIPT_DIR=%~dp0..\scripts"
if not exist "%SCRIPT_DIR%\force_stop_bot.ps1" set "SCRIPT_DIR=%~dp0scripts"
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\force_stop_bot.ps1"

echo.
echo Done. You can move or rename the BOT folder now.
pause

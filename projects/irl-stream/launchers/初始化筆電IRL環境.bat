@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0.."
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\setup_laptop_relay.ps1"
pause

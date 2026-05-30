@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0.."
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\export_laptop_relay_bundle.ps1"
pause

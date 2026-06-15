@echo off
set "PROJECT_DIR=%~dp0.."
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\cancel_autostart.ps1"

@echo off
set "PROJECT_DIR=%~dp0.."
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\setup_autostart.ps1"

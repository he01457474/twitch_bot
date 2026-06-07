@echo off
set "PROJECT_DIR=%~dp0.."
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\stop_secretary.ps1"

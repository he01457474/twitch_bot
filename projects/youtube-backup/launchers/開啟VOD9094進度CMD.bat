@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\monitor-vod9094-cmd.ps1"

if not exist "%SCRIPT%" (
    echo Missing monitor script:
    echo %SCRIPT%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
pause

@echo off
set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\status_irl.ps1"

if not exist "%SCRIPT%" (
  echo [ERROR] Missing status script:
  echo   %SCRIPT%
  echo.
  echo Run this file from the full project launchers folder.
  echo.
  pause
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%"
pause

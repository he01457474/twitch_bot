@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\setup_laptop_relay.ps1"

if not exist "%SCRIPT%" (
  echo [ERROR] Missing setup script:
  echo   %SCRIPT%
  echo.
  echo This launcher cannot run alone from Downloads.
  echo Use download_and_initialize_laptop_relay.bat first, or run this from:
  echo   projects\irl-stream\launchers\initialize_laptop_relay.bat
  echo.
  pause
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%"
pause

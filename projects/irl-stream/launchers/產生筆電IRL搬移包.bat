@echo off
set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\export_laptop_relay_bundle.ps1"

if not exist "%SCRIPT%" (
  echo [ERROR] Missing export script:
  echo   %SCRIPT%
  echo.
  echo This launcher cannot run alone from Downloads.
  echo Run this file from the full project launchers folder.
  echo.
  pause
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%"
pause

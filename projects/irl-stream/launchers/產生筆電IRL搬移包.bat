@echo off
chcp 65001 > nul
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

powershell -ExecutionPolicy Bypass -NoProfile -Command "& ([scriptblock]::Create([System.IO.File]::ReadAllText('%SCRIPT%', [System.Text.Encoding]::UTF8)))"
pause

@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\setup_laptop_relay.ps1"

if not exist "%SCRIPT%" (
  echo [錯誤] 找不到初始化腳本：
  echo   %SCRIPT%
  echo.
  echo 這個 bat 不能單獨放在下載資料夾執行。
  echo 請把整個 projects\irl-stream 資料夾放到筆電，再從下面位置執行：
  echo   projects\irl-stream\launchers\初始化筆電IRL環境.bat
  echo.
  pause
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%"
pause

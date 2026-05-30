@echo off
chcp 65001 > nul
set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\export_laptop_relay_bundle.ps1"

if not exist "%SCRIPT%" (
  echo [錯誤] 找不到搬移包腳本：
  echo   %SCRIPT%
  echo.
  echo 這個 bat 不能單獨放在下載資料夾執行。
  echo 請從原本工作目錄的下面位置執行：
  echo   projects\irl-stream\launchers\產生筆電IRL搬移包.bat
  echo.
  pause
  exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%SCRIPT%"
pause

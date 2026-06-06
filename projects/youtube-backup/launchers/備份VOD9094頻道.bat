@echo off
chcp 65001 >nul
setlocal

set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\backup-vod9094.ps1"
set "YTDLP=%PROJECT_DIR%\tools\yt-dlp.exe"

if not exist "%YTDLP%" (
    echo 找不到 yt-dlp.exe：
    echo %YTDLP%
    echo.
    echo 請先執行 Codex 建立的下載流程，或把 yt-dlp.exe 放到 tools 資料夾。
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo 找不到備份腳本：
    echo %SCRIPT%
    pause
    exit /b 1
)

echo 開始備份 VOD9094 YouTube 頻道公開影片...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"

echo.
echo 備份流程結束。若中途有失敗影片，可直接重新執行本檔案續跑。
pause

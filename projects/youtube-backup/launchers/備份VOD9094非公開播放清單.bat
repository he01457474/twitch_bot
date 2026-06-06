@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
set "SCRIPT=%PROJECT_DIR%\scripts\backup-vod9094-unlisted-playlist.ps1"
set "YTDLP=%PROJECT_DIR%\tools\yt-dlp.exe"

if not exist "%YTDLP%" (
    echo Missing yt-dlp:
    echo %YTDLP%
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo Missing backup script:
    echo %SCRIPT%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
pause

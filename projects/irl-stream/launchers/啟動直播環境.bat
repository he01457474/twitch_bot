@echo off
set "PROJECT_DIR=%~dp0.."
where wt.exe >nul 2>nul
if errorlevel 1 (
  start "StreamControl" powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\stream_start.ps1"
) else (
  wt -w new new-tab --title "StreamControl" -- powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\stream_start.ps1"
)
timeout /t 2 /nobreak >nul
powershell -ExecutionPolicy Bypass -NoProfile -File "%PROJECT_DIR%\scripts\restore_stream_size.ps1"

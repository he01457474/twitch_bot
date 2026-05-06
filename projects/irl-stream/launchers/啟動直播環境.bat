@echo off
set "PROJECT_DIR=%~dp0.."
wt -w new new-tab --title "StreamControl" -- powershell -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\stream_start.ps1"
timeout /t 2 /nobreak >nul
powershell -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\restore_stream_size.ps1"

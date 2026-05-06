@echo off
set "PROJECT_DIR=%~dp0.."
wt -w _new --title "StreamStop" -- powershell -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\stream_stop.ps1"
timeout /t 2 /nobreak >nul
powershell -ExecutionPolicy Bypass -File "%PROJECT_DIR%\scripts\restore_stream_size.ps1" -Title StreamStop

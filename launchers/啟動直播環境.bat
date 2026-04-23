@echo off
wt -w new new-tab --title "StreamControl" -- powershell -ExecutionPolicy Bypass -File "D:\tset\FlyCatClaude Code\scripts\stream_start.ps1"
timeout /t 2 /nobreak >nul
powershell -ExecutionPolicy Bypass -File "D:\tset\FlyCatClaude Code\scripts\restore_stream_size.ps1"

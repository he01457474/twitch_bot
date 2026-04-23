@echo off
wt -w _new --title "StreamStop" -- powershell -ExecutionPolicy Bypass -File "D:\tset\FlyCatClaude Code\scripts\stream_stop.ps1"
timeout /t 2 /nobreak >nul
powershell -ExecutionPolicy Bypass -File "D:\tset\FlyCatClaude Code\scripts\restore_stream_size.ps1" -Title StreamStop

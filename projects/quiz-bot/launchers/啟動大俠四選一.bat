@echo off
chcp 65001 >nul
"D:\tset\FlyCatClaude Code\.tools\python-3.13.3-embed\python.exe" "%~dp0..\tools\quiz_bot.py"
if %errorlevel% neq 0 pause

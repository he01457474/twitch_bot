@echo off
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup_restaurant_build_env.ps1
if errorlevel 1 pause & exit /b %errorlevel%
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_restaurant_bot.ps1
pause

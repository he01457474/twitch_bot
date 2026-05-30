@echo off
chcp 65001 > nul
echo FlyCat IRL laptop setup
echo.
echo Downloading bootstrap script from GitHub...
set "TMPSCRIPT=%TEMP%\flycat_bootstrap.ps1"
curl -fsSL "https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/bootstrap_laptop_relay.ps1" -o "%TMPSCRIPT%"
if errorlevel 1 (
    echo Download failed. Check your internet connection.
    pause
    exit /b 1
)
powershell -ExecutionPolicy Bypass -NoProfile -Command "& ([scriptblock]::Create([System.IO.File]::ReadAllText('%TMPSCRIPT%', [System.Text.Encoding]::UTF8)))"
del "%TMPSCRIPT%" 2>nul
pause

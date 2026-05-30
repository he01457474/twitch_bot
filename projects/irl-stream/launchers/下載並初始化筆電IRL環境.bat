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
powershell -NoProfile -Command "[System.IO.File]::WriteAllText('%TMPSCRIPT%', [System.IO.File]::ReadAllText('%TMPSCRIPT%', [System.Text.Encoding]::UTF8), (New-Object System.Text.UTF8Encoding($true)))"
powershell -ExecutionPolicy Bypass -NoProfile -File "%TMPSCRIPT%"
del "%TMPSCRIPT%" 2>nul
pause

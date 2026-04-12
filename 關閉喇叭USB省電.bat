@echo off
net session 2>NUL
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0usb_power_fix.ps1"
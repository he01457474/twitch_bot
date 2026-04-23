@echo off
net session 2>NUL
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\audio\usb_power_fix.ps1"
start "" /min C:\Users\he014\AppData\Local\Programs\Python\Python310\pythonw.exe "%~dp0..\scripts\audio\keepalive_halo.py"

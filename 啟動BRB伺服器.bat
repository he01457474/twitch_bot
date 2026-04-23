@echo off
chcp 65001 > nul
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0scripts\brb_server.ps1"

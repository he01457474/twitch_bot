@echo off
chcp 65001 > nul
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0..\scripts\update_dynu_ddns.ps1"

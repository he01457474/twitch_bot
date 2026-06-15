@echo off
schtasks /delete /tn "SecretaryBotAutoStart" /f
echo.
echo 已取消開機自動啟動。
pause

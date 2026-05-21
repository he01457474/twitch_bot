@echo off
chcp 65001 > nul
echo 安裝私人秘書所需套件...
"D:\tset\FlyCatClaude Code\.tools\python-3.13.3-embed\python.exe" -m pip install discord.py "google-genai>=1.0.0" requests beautifulsoup4 python-dotenv
echo.
echo 安裝完成，請關閉此視窗。
pause

@echo off
chcp 65001 > nul
echo 下載並初始化筆電 IRL 環境
echo.
echo 這個入口可以單獨放在下載資料夾執行。
echo 會從 GitHub 下載初始化腳本，並把專案準備到 D:\FlyCatClaude Code。
echo.
powershell -ExecutionPolicy Bypass -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $u='https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/bootstrap_laptop_relay.ps1'; iex (Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 30).Content"
pause

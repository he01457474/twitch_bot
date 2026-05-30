@echo off
chcp 65001 > nul
echo FlyCat IRL laptop setup
echo.
echo This launcher can run from Downloads.
echo It downloads the bootstrap script from GitHub.
echo.
powershell -ExecutionPolicy Bypass -NoProfile -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $u='https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/bootstrap_laptop_relay.ps1'; $c=(Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 30).Content; if ([string]::IsNullOrWhiteSpace($c)) { throw 'bootstrap download returned empty content' }; if ($c[0] -eq [char]0xFEFF) { $c=$c.Substring(1) }; iex $c"
pause

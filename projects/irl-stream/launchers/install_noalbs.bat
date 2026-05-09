@echo off
chcp 65001 > nul

powershell -ExecutionPolicy Bypass -NoProfile -Command "& { $url = 'https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/install_noalbs_core.ps1'; $f = Join-Path $env:TEMP 'install_noalbs_tmp.ps1'; try { Invoke-WebRequest $url -OutFile $f -UseBasicParsing } catch { Write-Host '[錯誤] 下載安裝腳本失敗，請確認網路連線後重試。' -ForegroundColor Red; Read-Host '按 Enter 關閉'; exit 1 }; & $f; Remove-Item $f -ErrorAction SilentlyContinue }"

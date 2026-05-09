@echo off
chcp 65001 > nul

powershell -ExecutionPolicy Bypass -NoProfile -Command "& { $url = 'https://raw.githubusercontent.com/he01457474/twitch_bot/master/projects/irl-stream/scripts/install_noalbs_core.ps1'; $f = Join-Path $env:TEMP 'install_noalbs_tmp.ps1'; try { $c = (Invoke-WebRequest $url -UseBasicParsing).Content; if ($c.StartsWith([char]0xFEFF)) { $c = $c.Substring(1) }; [System.IO.File]::WriteAllText($f, $c, (New-Object System.Text.UTF8Encoding $true)) } catch { Write-Host 'Download failed. Check your internet connection.' -ForegroundColor Red; Read-Host 'Press Enter to close'; exit 1 }; & $f; Remove-Item $f -ErrorAction SilentlyContinue }"
pause

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '   NOALBS 一鍵安裝設定工具   ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''

$twitchId = (Read-Host '① 你的 Twitch ID（英文帳號，例如 kevin123）').Trim().ToLower()

Write-Host ''
Write-Host '② 請到下面這個網址，用你的 Twitch 帳號登入後按 Connect，複製 oauth:... 這段' -ForegroundColor Yellow
Write-Host '   https://twitchapps.com/tmi/' -ForegroundColor Cyan
$twitchToken = (Read-Host '   貼上你的 Token（oauth:xxxxxxxxxx）').Trim()

Write-Host ''
$obsPassword = (Read-Host '③ 你的 OBS WebSocket 密碼（OBS → 工具 → WebSocket 伺服器設定）').Trim()

$installDir = "$env:USERPROFILE\Desktop\NOALBS_$twitchId"
$zipPath    = "$env:TEMP\noalbs.zip"
$noalbsUrl  = 'https://github.com/NOALBS/nginx-obs-automatic-low-bitrate-switching/releases/download/v2.16.1/noalbs-v2.16.1-x86_64-pc-windows-msvc.zip'

Write-Host ''
Write-Host '正在下載 NOALBS...' -ForegroundColor Cyan

try {
    Invoke-WebRequest -Uri $noalbsUrl -OutFile $zipPath -UseBasicParsing
} catch {
    Write-Host ''
    Write-Host '[錯誤] 下載失敗，請確認網路連線正常後重試。' -ForegroundColor Red
    Read-Host '按 Enter 關閉'
    exit 1
}

Write-Host '正在解壓縮...' -ForegroundColor Cyan
Expand-Archive -Path $zipPath -DestinationPath $installDir -Force
Remove-Item $zipPath -ErrorAction SilentlyContinue

$inner = Get-ChildItem $installDir -Directory | Select-Object -First 1
$noalbsPath = if ($inner) { $inner.FullName } else { $installDir }

Write-Host '下載完成' -ForegroundColor Green

@"
TWITCH_BOT_USERNAME=$twitchId
TWITCH_BOT_OAUTH=$twitchToken
"@ | Set-Content -Path "$noalbsPath\.env" -Encoding UTF8

@"
{
  "user": { "id": null, "name": "$twitchId", "passwordHash": null },
  "switcher": {
    "bitrateSwitcherEnabled": true,
    "onlySwitchWhenStreaming": true,
    "instantlySwitchOnRecover": true,
    "autoSwitchNotification": true,
    "retryAttempts": 5,
    "triggers": { "low": 800, "rtt": 2500, "offline": 100 },
    "switchingScenes": { "normal": "IRL", "low": "lowB", "offline": "BRB" },
    "streamServers": [{
      "streamServer": {
        "type": "Mediamtx",
        "statsUrl": "http://flycat.ddns.net:9997/v3/paths/get/$twitchId"
      },
      "name": "MediaMTX", "priority": 1,
      "overrideScenes": null, "dependsOn": null, "enabled": true
    }]
  },
  "software": { "type": "Obs", "host": "localhost", "password": "$obsPassword", "port": 4455 },
  "chat": {
    "platform": "Twitch", "username": "$twitchId", "admins": ["$twitchId"],
    "ignoreUsers": [], "language": "EN", "prefix": "!",
    "enablePublicCommands": false, "enableModCommands": true,
    "enableAutoStopStreamOnHostOrRaid": false, "announceRaidOnAutoStop": false,
    "commands": {
      "Fix":    { "permission": "Mod", "userPermissions": null, "alias": ["f"] },
      "Switch": { "permission": "Mod", "userPermissions": null, "alias": ["ss"] },
      "Bitrate":{ "permission": null,  "userPermissions": null, "alias": ["b"] },
      "Start":  { "permission": "Mod", "userPermissions": null, "alias": ["start"] },
      "Stop":   { "permission": "Mod", "userPermissions": null, "alias": ["stop"] }
    }
  },
  "optionalScenes": { "starting": null, "ending": null, "privacy": null, "refresh": null },
  "optionalOptions": {
    "twitchTranscodingCheck": false, "twitchTranscodingRetries": 5,
    "twitchTranscodingDelaySeconds": 15, "offlineTimeout": null,
    "recordWhileStreaming": false,
    "switchToStartingSceneOnStreamStart": false,
    "switchFromStartingSceneToLiveScene": false
  }
}
"@ | Set-Content -Path "$noalbsPath\config.json" -Encoding UTF8

Write-Host ''
Write-Host '=============================' -ForegroundColor Green
Write-Host '         安裝完成！          ' -ForegroundColor Green
Write-Host '=============================' -ForegroundColor Green
Write-Host ''
Write-Host "設定檔位置：$noalbsPath" -ForegroundColor Cyan
Write-Host ''
Write-Host '接下來：' -ForegroundColor Yellow
Write-Host '  1. 確認 OBS 已開啟且 WebSocket 功能有啟用'
Write-Host '  2. 雙擊資料夾裡的 noalbs.exe'
Write-Host '  3. 看到沒有紅色錯誤就代表成功了'
Write-Host ''

Start-Process explorer.exe $noalbsPath
Start-Process 'https://flycatirl.netlify.app/'

Read-Host '按 Enter 關閉'

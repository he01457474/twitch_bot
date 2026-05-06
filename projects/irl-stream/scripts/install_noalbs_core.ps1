chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$relayHost = 'flycat.ddns.net'
$srtPort = 5002
$statsPort = 9997
$tokenUrl = 'https://irlhosting.com/tmi/'
$noalbsUrl = 'https://github.com/NOALBS/nginx-obs-automatic-low-bitrate-switching/releases/download/v2.16.1/noalbs-v2.16.1-x86_64-pc-windows-msvc.zip'

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '   戶外直播一條龍設定工具   ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '這是借用者電腦用的工具，會幫你產生 NOALBS 設定和直播時要填的網址。' -ForegroundColor Yellow
Write-Host '中繼伺服器由管理員提供，你的電腦不需要安裝 Docker 或 MediaMTX。' -ForegroundColor Yellow
Write-Host ''
Write-Host '開始前先準備好：' -ForegroundColor Cyan
Write-Host '  1. 你的 Twitch 英文帳號'
Write-Host '  2. Twitch Bot Token（等等會開網頁讓你拿）'
Write-Host '  3. OBS WebSocket 密碼'
Write-Host ''

do {
    $twitchId = (Read-Host '① 你的 Twitch ID（英文帳號，例如 kevin123）').Trim().ToLower()
    if (-not $twitchId) { Write-Host '  請填入 Twitch ID' -ForegroundColor Red }
} while (-not $twitchId)

Write-Host ''
Write-Host '② 請到下面這個網址，用你的 Twitch 帳號登入後按 Connect，複製 oauth:... 這段' -ForegroundColor Yellow
Write-Host "   $tokenUrl" -ForegroundColor Cyan
Start-Process $tokenUrl
do {
    $twitchToken = (Read-Host '   貼上你的 Token（oauth:xxxxxxxxxx）').Trim()
    if (-not $twitchToken) {
        Write-Host '  請填入 Token' -ForegroundColor Red
    } elseif ($twitchToken -notlike 'oauth:*') {
        Write-Host '  Token 應該要以 oauth: 開頭' -ForegroundColor Red
    }
} while (-not $twitchToken -or $twitchToken -notlike 'oauth:*')

Write-Host ''
Write-Host '③ OBS WebSocket 密碼在 OBS → 工具 → WebSocket 伺服器設定。' -ForegroundColor Yellow
do {
    $obsPassword = (Read-Host '   貼上你的 OBS WebSocket 密碼').Trim()
    if (-not $obsPassword) { Write-Host '  請填入 OBS WebSocket 密碼' -ForegroundColor Red }
} while (-not $obsPassword)

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installDir = Join-Path (Join-Path $projectRoot "tools") "NOALBS_$twitchId"
$zipPath = "$env:TEMP\noalbs.zip"
$publishStreamId = "publish:$twitchId"
$phoneUrl = "srt://$relayHost`:$srtPort"
$obsInputUrl = "srt://$relayHost`:$srtPort`?streamid=read:$twitchId"
$statsUrl = "http://$relayHost`:$statsPort/v3/paths/get/$twitchId"

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
        "statsUrl": "$statsUrl"
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

@"
@echo off
cd /d "%~dp0"
start "" noalbs.exe
"@ | Set-Content -Path (Join-Path $noalbsPath "啟動_NOALBS.bat") -Encoding UTF8

@"
@echo off
chcp 65001 > nul
echo ========================================
echo   每次直播順序
echo ========================================
echo.
echo 1. 先開 OBS
echo 2. 確認 OBS 有 IRL / lowB / BRB 三個場景
echo 3. 手機開始推流
echo 4. 等手機連上後，回 Twitch 聊天室打 !start
echo.
echo 這個視窗會啟動 NOALBS。
echo 如果 NOALBS 顯示 Connected to OBS，代表連上 OBS。
echo.
pause
start "" "%~dp0啟動_NOALBS.bat"
"@ | Set-Content -Path (Join-Path $noalbsPath "每次直播開這個.bat") -Encoding UTF8

@"
戶外直播設定資料
================

你的 Twitch ID：
$twitchId

手機推流設定
------------
URL：
$phoneUrl

Stream ID：
$publishStreamId

OBS 媒體來源
------------
輸入：
$obsInputUrl

NOALBS 監測網址
---------------
$statsUrl

每次直播順序
------------
1. 開 OBS
2. 執行「每次直播開這個.bat」
3. 手機開始推流
4. Twitch 聊天室打 !start

如果手機一直 Connecting，先問管理員中繼伺服器是否有開。
如果 NOALBS 連不上 OBS，確認 OBS 已開啟 WebSocket，且密碼填對。
"@ | Set-Content -Path (Join-Path $noalbsPath "我的直播設定.txt") -Encoding UTF8

Write-Host ''
Write-Host '=============================' -ForegroundColor Green
Write-Host '         安裝完成！          ' -ForegroundColor Green
Write-Host '=============================' -ForegroundColor Green
Write-Host ''
Write-Host "設定檔位置：$noalbsPath" -ForegroundColor Cyan
Write-Host ''
Write-Host '接下來：' -ForegroundColor Yellow
Write-Host '  1. 打開「我的直播設定.txt」，照裡面的資料填手機和 OBS'
Write-Host '  2. 之後每次直播，雙擊「每次直播開這個.bat」'
Write-Host '  3. 手機開始推流後，到 Twitch 聊天室打 !start'
Write-Host ''
Write-Host '手機推流 URL：' -ForegroundColor Cyan
Write-Host "  $phoneUrl"
Write-Host '手機 Stream ID：' -ForegroundColor Cyan
Write-Host "  $publishStreamId"
Write-Host 'OBS 媒體來源輸入：' -ForegroundColor Cyan
Write-Host "  $obsInputUrl"
Write-Host ''

Start-Process explorer.exe $noalbsPath
Start-Process 'https://flycatirl.netlify.app/'

Read-Host '按 Enter 關閉'

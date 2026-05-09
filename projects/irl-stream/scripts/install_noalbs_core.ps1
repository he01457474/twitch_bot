chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$noalbsUrl = 'https://github.com/NOALBS/nginx-obs-automatic-low-bitrate-switching/releases/download/v2.16.1/noalbs-v2.16.1-x86_64-pc-windows-msvc.zip'
$tokenUrl  = 'https://irlhosting.com/tmi/'

function Read-WithDefault {
    param([string]$Prompt, [string]$Default)
    $input = (Read-Host "$Prompt（預設：$Default）").Trim()
    if (-not $input) { return $Default }
    return $input
}

function Get-StatsUrl {
    param([string]$ServerType, [string]$Host, [string]$Path)
    switch ($ServerType) {
        'Mediamtx'        { return "http://${Host}:9997/v3/paths/get/$Path" }
        'NginxRtmp'       { return "http://${Host}:8080/stat" }
        'NodeMediaServer' { return "http://${Host}:8000/api/streams" }
        'SrtLiveServer'   { return "http://${Host}:8181/stats" }
        default           { return "http://${Host}:9997/v3/paths/get/$Path" }
    }
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '   戶外直播一條龍設定工具   ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '這是借用者電腦用的工具，會幫你自動下載 NOALBS，並產生 .env、config.json 和啟動檔。' -ForegroundColor Yellow
Write-Host '中繼伺服器由管理員提供，你的電腦不需要安裝 Docker 或 MediaMTX。' -ForegroundColor Yellow
Write-Host ''
Write-Host '開始前先準備好：' -ForegroundColor Cyan
Write-Host '  1. 你的 Twitch 英文帳號'
Write-Host '  2. Twitch Bot Token（等等會開網頁讓你拿）'
Write-Host '  3. OBS WebSocket 密碼'
Write-Host ''

# ① Twitch ID
do {
    $twitchId = (Read-Host '① 你的 Twitch ID（英文帳號，例如 kevin123）').Trim().ToLower()
    if (-not $twitchId) { Write-Host '  請填入 Twitch ID' -ForegroundColor Red }
} while (-not $twitchId)

# ② Bot Token
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

# ③ 伺服器選擇
Write-Host ''
Write-Host '③ 選擇中繼伺服器' -ForegroundColor Yellow
Write-Host '  1. flycat 伺服器（管理員 flycat 提供，預設選這個）'
Write-Host '  2. 自訂伺服器（其他管理員提供的伺服器位址）'
do {
    $serverChoice = (Read-Host '   請輸入 1 或 2').Trim()
    if ($serverChoice -notin @('1','2')) { Write-Host '  請輸入 1 或 2' -ForegroundColor Red }
} while ($serverChoice -notin @('1','2'))

if ($serverChoice -eq '1') {
    $serverHost = 'flycat.ddns.net'
    $serverType = 'Mediamtx'
    $statsUrl   = Get-StatsUrl -ServerType $serverType -Host $serverHost -Path $twitchId
    Write-Host "  伺服器：$serverHost（MediaMTX）" -ForegroundColor Green
} else {
    Write-Host ''
    do {
        $serverHost = (Read-Host '   伺服器位址（例如 abc.ddns.net 或 192.168.1.1）').Trim()
        if (-not $serverHost) { Write-Host '  請填入伺服器位址' -ForegroundColor Red }
    } while (-not $serverHost)

    Write-Host ''
    Write-Host '   伺服器類型（不確定的話問管理員）：' -ForegroundColor Yellow
    Write-Host '   1. MediaMTX（最常見）'
    Write-Host '   2. RTMP'
    Write-Host '   3. NodeMediaServer'
    Write-Host '   4. SRT Live Server'
    do {
        $typeChoice = (Read-Host '   請輸入 1-4').Trim()
        if ($typeChoice -notin @('1','2','3','4')) { Write-Host '  請輸入 1 到 4' -ForegroundColor Red }
    } while ($typeChoice -notin @('1','2','3','4'))

    $serverType = @{ '1'='Mediamtx'; '2'='NginxRtmp'; '3'='NodeMediaServer'; '4'='SrtLiveServer' }[$typeChoice]
    $statsUrl   = Get-StatsUrl -ServerType $serverType -Host $serverHost -Path $twitchId
    Write-Host "  伺服器：$serverHost（$serverType）" -ForegroundColor Green
}

# ④ OBS WebSocket 密碼
Write-Host ''
Write-Host '④ OBS WebSocket 密碼在 OBS → 工具 → WebSocket 伺服器設定。' -ForegroundColor Yellow
do {
    $obsPassword = (Read-Host '   貼上你的 OBS WebSocket 密碼').Trim()
    if (-not $obsPassword) { Write-Host '  請填入 OBS WebSocket 密碼' -ForegroundColor Red }
} while (-not $obsPassword)

# ⑤ OBS 場景名稱
Write-Host ''
Write-Host '⑤ OBS 場景名稱（直接按 Enter 使用括號內的預設值）' -ForegroundColor Yellow
$sceneNormal  = Read-WithDefault '   正常畫面場景名稱' 'IRL'
$sceneLow     = Read-WithDefault '   低畫質場景名稱' 'lowB'
$sceneOffline = Read-WithDefault '   離線場景名稱' 'BRB'

# 預設安裝目錄（找不到現有安裝時使用）
$installDir = Join-Path $env:USERPROFILE "NOALBS_$twitchId"
$zipPath    = "$env:TEMP\noalbs.zip"

# 在指定目錄內找 noalbs.exe（可能在子資料夾一層）
function Find-ExeInDir {
    param([string]$Dir)
    if (-not (Test-Path $Dir)) { return $null }
    $direct = Join-Path $Dir 'noalbs.exe'
    if (Test-Path $direct) { return $direct }
    $sub = Get-ChildItem $Dir -Directory -ErrorAction SilentlyContinue |
           ForEach-Object { Join-Path $_.FullName 'noalbs.exe' } |
           Where-Object { Test-Path $_ } |
           Select-Object -First 1
    return $sub
}

# 多點偵測：依序掃常見位置
$searchDirs = @(
    $installDir,
    (Join-Path $env:USERPROFILE 'Desktop'),
    (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'Documents')
) + (Get-ChildItem $env:USERPROFILE -Directory -ErrorAction SilentlyContinue |
     Where-Object { $_.Name -imatch 'noalbs' } |
     Select-Object -ExpandProperty FullName)

$existingExe = $searchDirs | ForEach-Object { Find-ExeInDir $_ } | Where-Object { $_ } | Select-Object -First 1

if ($existingExe) {
    Write-Host ''
    Write-Host "偵測到已安裝的 NOALBS：$existingExe，略過下載。" -ForegroundColor Green
    $noalbsPath = Split-Path $existingExe
} else {
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

    $exePath    = Find-ExeInDir $installDir
    $noalbsPath = if ($exePath) { Split-Path $exePath } else { $installDir }
    Write-Host '下載完成' -ForegroundColor Green
}

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
    "switchingScenes": { "normal": "$sceneNormal", "low": "$sceneLow", "offline": "$sceneOffline" },
    "streamServers": [{
      "streamServer": {
        "type": "$serverType",
        "statsUrl": "$statsUrl"
      },
      "name": "$serverType", "priority": 0,
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

Write-Host ''
Write-Host '=============================' -ForegroundColor Green
Write-Host '         安裝完成！          ' -ForegroundColor Green
Write-Host '=============================' -ForegroundColor Green
Write-Host ''
Write-Host "設定檔位置：$noalbsPath" -ForegroundColor Cyan
Write-Host ''
Write-Host '接下來：' -ForegroundColor Yellow
Write-Host '  1. 照網頁教學設定手機和 OBS'
Write-Host '  2. 之後每次直播，先開 OBS，再雙擊「啟動_NOALBS.bat」'
Write-Host '  3. 手機開始推流後，到 Twitch 聊天室打 !start'
Write-Host ''

Start-Process explorer.exe $noalbsPath
Start-Process 'https://flycatirl.netlify.app/'

Read-Host '按 Enter 關閉'

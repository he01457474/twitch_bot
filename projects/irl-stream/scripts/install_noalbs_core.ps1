param([string]$InstallDir = '')
if ($InstallDir) { $InstallDir = $InstallDir.TrimEnd('\').TrimEnd('/') }

$ErrorActionPreference = 'Stop'

$settingsScript = Join-Path $PSScriptRoot 'irl_settings.ps1'
if (Test-Path $settingsScript) {
    . $settingsScript
} else {
    function Get-IrlRelayHost {
        return 'flycatirl.ddnsgeek.com'
    }
}

$noalbsUrl = 'https://github.com/NOALBS/nginx-obs-automatic-low-bitrate-switching/releases/download/v2.16.1/noalbs-v2.16.1-x86_64-pc-windows-msvc.zip'
$tokenUrl  = 'https://irlhosting.com/tmi/'

function Read-WithDefault {
    param([string]$Prompt, [string]$Default)
    $input = (Read-Host "$Prompt（預設：$Default）").Trim()
    if (-not $input) { return $Default }
    return $input
}

function Get-StatsUrl {
    param([string]$ServerType, [string]$HostName, [string]$Path)
    switch ($ServerType) {
        'Mediamtx'        { return "http://${HostName}:9997/v3/paths/get/$Path" }
        'NginxRtmp'       { return "http://${HostName}:8080/stat" }
        'NodeMediaServer' { return "http://${HostName}:8000/api/streams" }
        'SrtLiveServer'   { return "http://${HostName}:8181/stats" }
        default           { return "http://${HostName}:9997/v3/paths/get/$Path" }
    }
}

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

function Get-SafeFolderName {
    param([string]$Name)
    $safe = $Name
    foreach ($char in [System.IO.Path]::GetInvalidFileNameChars()) {
        $safe = $safe.Replace($char, '_')
    }
    return $safe
}

function Flatten-NoalbsInstallDir {
    param([string]$Dir)

    $directExe = Join-Path $Dir 'noalbs.exe'
    if (Test-Path $directExe) { return $Dir }

    $subDirs = @(Get-ChildItem $Dir -Directory -ErrorAction SilentlyContinue)
    $noalbsSubDir = $subDirs |
        Where-Object { Test-Path (Join-Path $_.FullName 'noalbs.exe') } |
        Select-Object -First 1

    if (-not $noalbsSubDir) { return $Dir }

    Write-Host '正在整理 NOALBS 檔案位置...' -ForegroundColor DarkGray
    Get-ChildItem $noalbsSubDir.FullName -Force | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $Dir -Force
    }

    if (-not (Get-ChildItem $noalbsSubDir.FullName -Force -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $noalbsSubDir.FullName -Force -ErrorAction SilentlyContinue
    }

    return $Dir
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '   戶外直播一條龍設定工具   ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '正在偵測...' -ForegroundColor DarkGray

# 掃描常見位置（bat 所在目錄優先）
$searchDirs = @(
    $InstallDir,
    $env:USERPROFILE,
    (Join-Path $env:USERPROFILE 'Desktop'),
    (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE 'Documents')
) | Where-Object { $_ } | Select-Object -Unique
if ($InstallDir -and (Test-Path $InstallDir)) {
    $searchDirs += Get-ChildItem $InstallDir -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -imatch '^NOALBS' } |
                   Select-Object -ExpandProperty FullName
}
$searchDirs += Get-ChildItem $env:USERPROFILE -Directory -ErrorAction SilentlyContinue |
               Where-Object { $_.Name -imatch 'noalbs' } |
               Select-Object -ExpandProperty FullName

$existingExe = $searchDirs | ForEach-Object { Find-ExeInDir $_ } | Where-Object { $_ } | Select-Object -First 1

# ── 已有安裝 ──────────────────────────────────────────────
if ($existingExe) {
    $noalbsPath = Split-Path $existingExe

    # 從 .env 讀出 Twitch ID
    $twitchId = ''
    $envFile = Join-Path $noalbsPath '.env'
    if (Test-Path $envFile) {
        $line = Get-Content $envFile | Where-Object { $_ -match '^TWITCH_BOT_USERNAME=' }
        if ($line) { $twitchId = ($line -replace '^TWITCH_BOT_USERNAME=', '').Trim() }
    }

    Write-Host "偵測到已安裝：$noalbsPath" -ForegroundColor Green
    if ($twitchId) { Write-Host "Twitch ID：$twitchId" -ForegroundColor DarkGray }
    Write-Host ''
    Write-Host '  1. 更新設定'
    Write-Host '  2. 移除安裝'
    Write-Host ''
    do {
        $action = (Read-Host '請選擇').Trim()
        if ($action -notin @('1','2')) { Write-Host '  請輸入 1 或 2' -ForegroundColor Red }
    } while ($action -notin @('1','2'))

    if ($action -eq '2') {
        $noalbsFiles = @('noalbs.exe', 'config.json', '.env', '啟動_NOALBS.bat', '關閉_NOALBS.bat')
        Write-Host ''
        Write-Host "即將刪除 $noalbsPath 裡的 NOALBS 檔案" -ForegroundColor Yellow
        $confirm = (Read-Host '確認刪除？（輸入 y 確認）').Trim().ToLower()
        if ($confirm -ne 'y') {
            Write-Host '已取消。' -ForegroundColor DarkGray
            Read-Host '按 Enter 關閉'
            exit 0
        }
        $proc = Get-Process 'noalbs' -ErrorAction SilentlyContinue
        if ($proc) { Stop-Process -Name 'noalbs' -Force; Write-Host 'NOALBS 已停止' -ForegroundColor Green }
        foreach ($f in $noalbsFiles) {
            $fp = Join-Path $noalbsPath $f
            if (Test-Path $fp) { Remove-Item $fp -Force -ErrorAction SilentlyContinue }
        }
        $remaining = Get-ChildItem $noalbsPath -ErrorAction SilentlyContinue
        if (-not $remaining) { Remove-Item $noalbsPath -Force -ErrorAction SilentlyContinue }
        Write-Host ''
        Write-Host '=============================' -ForegroundColor Green
        Write-Host '         移除完成！          ' -ForegroundColor Green
        Write-Host '=============================' -ForegroundColor Green
        Write-Host ''
        Write-Host "已刪除：$noalbsPath" -ForegroundColor Cyan
        Read-Host '按 Enter 關閉'
        exit 0
    }

    # 更新設定：若 .env 沒讀到 ID 才補問
    if (-not $twitchId) {
        do {
            $twitchId = (Read-Host 'Twitch ID').Trim().ToLower()
            if (-not $twitchId) { Write-Host '  請填入 Twitch ID' -ForegroundColor Red }
        } while (-not $twitchId)
    }
    $installDir = $noalbsPath

# ── 全新安裝 ──────────────────────────────────────────────
} else {
    Write-Host '未偵測到已安裝的 NOALBS，開始全新安裝。' -ForegroundColor DarkGray
    Write-Host ''
    do {
        $twitchId = (Read-Host 'Twitch ID（英文帳號，例如 kevin123）').Trim().ToLower()
        if (-not $twitchId) { Write-Host '  請填入 Twitch ID' -ForegroundColor Red }
    } while (-not $twitchId)
    $safeTwitchId = Get-SafeFolderName $twitchId
    $installBaseDir = if ($InstallDir) { $InstallDir } else { $env:USERPROFILE }
    $installDir = Join-Path $installBaseDir "NOALBS_$safeTwitchId"
    Write-Host "安裝位置：$installDir" -ForegroundColor DarkGray
}

# ── 安裝 / 更新共用流程 ────────────────────────────────────
Write-Host ''
Write-Host '請準備好：Twitch Bot Token、OBS WebSocket 密碼' -ForegroundColor Cyan
Write-Host ''

# Bot Token
Write-Host '請到下面這個網址，用你的 Twitch 帳號登入後按 Connect，複製 oauth:... 這段' -ForegroundColor Yellow
Write-Host "   $tokenUrl" -ForegroundColor Cyan
Start-Process $tokenUrl
do {
    $twitchToken = (Read-Host '貼上你的 Token（oauth:xxxxxxxxxx）').Trim()
    if (-not $twitchToken) {
        Write-Host '  請填入 Token' -ForegroundColor Red
    } elseif ($twitchToken -notlike 'oauth:*') {
        Write-Host '  Token 應該要以 oauth: 開頭' -ForegroundColor Red
    }
} while (-not $twitchToken -or $twitchToken -notlike 'oauth:*')

# 伺服器選擇
Write-Host ''
Write-Host '選擇中繼伺服器' -ForegroundColor Yellow
Write-Host '  1. flycat 伺服器（管理員 flycat 提供，預設選這個）'
Write-Host '  2. 自訂伺服器（其他管理員提供的伺服器位址）'
do {
    $serverChoice = (Read-Host '   請輸入 1 或 2').Trim()
    if ($serverChoice -notin @('1','2')) { Write-Host '  請輸入 1 或 2' -ForegroundColor Red }
} while ($serverChoice -notin @('1','2'))

if ($serverChoice -eq '1') {
    $serverHost = Get-IrlRelayHost
    $serverType = 'Mediamtx'
    $statsUrl   = Get-StatsUrl -ServerType $serverType -HostName $serverHost -Path $twitchId
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
    $statsUrl   = Get-StatsUrl -ServerType $serverType -HostName $serverHost -Path $twitchId
    Write-Host "  伺服器：$serverHost（$serverType）" -ForegroundColor Green
}

# OBS WebSocket 密碼
Write-Host ''
Write-Host 'OBS WebSocket 密碼在 OBS → 工具 → WebSocket 伺服器設定。' -ForegroundColor Yellow
do {
    $obsPassword = (Read-Host '   貼上你的 OBS WebSocket 密碼').Trim()
    if (-not $obsPassword) { Write-Host '  請填入 OBS WebSocket 密碼' -ForegroundColor Red }
} while (-not $obsPassword)

# OBS 場景名稱
Write-Host ''
Write-Host 'OBS 場景名稱（直接按 Enter 使用括號內的預設值）' -ForegroundColor Yellow
$sceneNormal  = Read-WithDefault '   正常畫面場景名稱' 'IRL'
$sceneLow     = Read-WithDefault '   低畫質場景名稱' 'lowB'
$sceneOffline = Read-WithDefault '   離線場景名稱' 'BRB'

# 下載（若尚未安裝）
$zipPath = "$env:TEMP\noalbs.zip"
if ($existingExe) {
    Write-Host ''
    Write-Host '程式已存在，略過下載，直接更新設定。' -ForegroundColor Green
} else {
    Write-Host ''
    Write-Host '正在下載 NOALBS...' -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri $noalbsUrl -OutFile $zipPath -UseBasicParsing
    } catch {
        Write-Host '[錯誤] 下載失敗，請確認網路連線正常後重試。' -ForegroundColor Red
        Read-Host '按 Enter 關閉'
        exit 1
    }
    Write-Host '正在解壓縮...' -ForegroundColor Cyan
    Expand-Archive -Path $zipPath -DestinationPath $installDir -Force
    Remove-Item $zipPath -ErrorAction SilentlyContinue
    $noalbsPath = Flatten-NoalbsInstallDir $installDir
    $exePath    = Find-ExeInDir $noalbsPath
    if (-not $exePath) {
        Write-Host '[錯誤] 解壓縮完成，但找不到 noalbs.exe。' -ForegroundColor Red
        Read-Host '按 Enter 關閉'
        exit 1
    }
    Write-Host '下載完成' -ForegroundColor Green
}

# 寫入設定檔（全部用無 BOM UTF-8，避免 Rust JSON parser 解析失敗）
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

$envContent = @"
TWITCH_BOT_USERNAME=$twitchId
TWITCH_BOT_OAUTH=$twitchToken
"@
[System.IO.File]::WriteAllText("$noalbsPath\.env", $envContent, $utf8NoBom)

$configContent = @"
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
"@
[System.IO.File]::WriteAllText("$noalbsPath\config.json", $configContent, $utf8NoBom)

$batContent = @"
@echo off
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process 'noalbs.exe' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
echo NOALBS 已啟動。
timeout /t 15 >nul
"@
[System.IO.File]::WriteAllText((Join-Path $noalbsPath "啟動_NOALBS.bat"), $batContent, $utf8NoBom)

$stopBatContent = @"
@echo off
taskkill /F /IM noalbs.exe /T >nul 2>&1
if errorlevel 1 (
    echo NOALBS 未在執行中。
) else (
    echo NOALBS 已關閉。
)
timeout /t 2 >nul
"@
[System.IO.File]::WriteAllText((Join-Path $noalbsPath "關閉_NOALBS.bat"), $stopBatContent, $utf8NoBom)

Write-Host ''
Write-Host '=============================' -ForegroundColor Green
Write-Host '         完成！              ' -ForegroundColor Green
Write-Host '=============================' -ForegroundColor Green
Write-Host ''
Write-Host "設定檔位置：$noalbsPath" -ForegroundColor Cyan
Write-Host ''
Write-Host '接下來：' -ForegroundColor Yellow
Write-Host '  1. 照網頁教學設定手機和 OBS'
Write-Host '  2. 之後每次直播，先開 OBS，再雙擊「啟動_NOALBS.bat」'
Write-Host '  3. 手機開始推流後，到 Twitch 聊天室打 !start'
Write-Host '  4. 要關閉 NOALBS，就關掉 noalbs.exe 視窗；看不到視窗時到工作管理員結束 noalbs.exe'
Write-Host ''

Start-Process explorer.exe $noalbsPath
Start-Process 'https://flycatirl.netlify.app/'

Read-Host '按 Enter 關閉'

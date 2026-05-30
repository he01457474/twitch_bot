chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$targetRoot = 'D:\FlyCatClaude Code'
$repoUrl = 'https://github.com/he01457474/twitch_bot/archive/refs/heads/master.zip'
$zipPath = Join-Path $env:TEMP 'flycat_twitch_bot_master.zip'
$extractRoot = Join-Path $env:TEMP ('flycat_twitch_bot_' + [Guid]::NewGuid().ToString('N'))

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '  下載並初始化筆電 IRL 環境  ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '這個入口可以單獨放在下載資料夾執行。'
Write-Host "它會下載主 repo 到：$targetRoot" -ForegroundColor Yellow
Write-Host ''

$rawAnswer = Read-Host '輸入 y 開始下載 / 更新專案，其他按鍵取消'
$answer = if ($null -eq $rawAnswer) { '' } else { $rawAnswer.Trim().ToLower() }
if ($answer -ne 'y') {
    Write-Host '已取消。' -ForegroundColor DarkGray
    exit 0
}

try {
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null

    Write-Host '正在下載專案...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri $repoUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 120

    Write-Host '正在解壓縮...' -ForegroundColor Cyan
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

    $sourceRoot = Get-ChildItem -LiteralPath $extractRoot -Directory | Select-Object -First 1
    if (-not $sourceRoot) {
        throw '下載內容不完整，找不到專案資料夾。'
    }

    if (Test-Path -LiteralPath $targetRoot) {
        Write-Host "目標資料夾已存在，將保留 config 私有資料並更新專案檔案：$targetRoot" -ForegroundColor Yellow
    } else {
        New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    }

    $robocopyArgs = @(
        $sourceRoot.FullName,
        $targetRoot,
        '/E',
        '/XD',
        '.git',
        'config',
        '/NFL',
        '/NDL',
        '/NJH',
        '/NJS',
        '/NC',
        '/NS'
    )
    & robocopy @robocopyArgs | Out-Null
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy 失敗，代碼：$code"
    }

    $launcher = Join-Path $targetRoot 'projects\irl-stream\launchers\初始化筆電IRL環境.bat'
    if (-not (Test-Path -LiteralPath $launcher)) {
        throw "找不到初始化入口：$launcher"
    }

    Write-Host ''
    Write-Host '專案已準備完成，正在開啟初始化腳本...' -ForegroundColor Green
    Start-Process -FilePath $launcher
} finally {
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$repoUrl = 'https://github.com/he01457474/twitch_bot/archive/refs/heads/master.zip'
$zipPath = Join-Path $env:TEMP 'flycat_twitch_bot_master.zip'
$extractRoot = Join-Path $env:TEMP ('flycat_twitch_bot_' + [Guid]::NewGuid().ToString('N'))

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '  FlyCat IRL Laptop Setup    ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'This downloads only the IRL relay files (not the full bot project).'
Write-Host ''

$rawPath = Read-Host 'Install path (e.g. D:\FlyCatIRL)'
$targetRoot = $rawPath.Trim().Trim('"')
if (-not $targetRoot) {
    Write-Host 'No path entered. Cancelled.' -ForegroundColor DarkGray
    exit 0
}

Write-Host ''
Write-Host "Install to: $targetRoot" -ForegroundColor Yellow
$rawAnswer = Read-Host 'Type y to download, anything else to cancel'
$answer = if ($null -eq $rawAnswer) { '' } else { $rawAnswer.Trim().ToLower() }
if ($answer -ne 'y') {
    Write-Host 'Cancelled.' -ForegroundColor DarkGray
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

    Write-Host 'Downloading IRL files...' -ForegroundColor Cyan
    Invoke-WebRequest -Uri $repoUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 120

    Write-Host 'Extracting...' -ForegroundColor Cyan
    Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

    $repoDir = Get-ChildItem -LiteralPath $extractRoot -Directory | Select-Object -First 1
    if (-not $repoDir) {
        throw 'Download incomplete: repo folder not found.'
    }

    $irlSource = Join-Path $repoDir.FullName 'projects\irl-stream'
    if (-not (Test-Path -LiteralPath $irlSource)) {
        throw "IRL project folder not found in download: $irlSource"
    }

    if (Test-Path -LiteralPath $targetRoot) {
        Write-Host "Target folder exists. Updating files (config folder preserved): $targetRoot" -ForegroundColor Yellow
    } else {
        New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    }

    $robocopyArgs = @(
        $irlSource,
        $targetRoot,
        '/E',
        '/XD', 'config',
        '/NFL', '/NDL', '/NJH', '/NJS', '/NC', '/NS'
    )
    & robocopy @robocopyArgs | Out-Null
    $code = $LASTEXITCODE
    if ($code -ge 8) {
        throw "robocopy failed with code: $code"
    }

    $launcher = Join-Path $targetRoot 'launchers\初始化筆電IRL環境.bat'
    if (-not (Test-Path -LiteralPath $launcher)) {
        throw "Setup launcher not found: $launcher"
    }

    Write-Host ''
    Write-Host 'Download complete. Opening setup...' -ForegroundColor Green
    Start-Process -FilePath $launcher
} finally {
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $extractRoot) {
        Remove-Item -LiteralPath $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

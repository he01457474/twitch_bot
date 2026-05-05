$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Entry = Join-Path $Root "tools\restaurant_bot.py"
$Dist = Join-Path $Root "dist\restaurant_bot_release"
$Work = Join-Path $Root "build\restaurant_bot"
$Spec = Join-Path $Root "build"

if (-not (Test-Path $Entry)) {
    throw "Entry file not found: $Entry"
}

if (Test-Path $Dist) {
    Remove-Item -LiteralPath $Dist -Recurse -Force
}

py -3.13 -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name restaurant_bot `
    --distpath $Dist `
    --workpath $Work `
    --specpath $Spec `
    --hidden-import winsdk.windows.media.ocr `
    --hidden-import winsdk.windows.globalization `
    --hidden-import winsdk.windows.graphics.imaging `
    --hidden-import winsdk.windows.storage.streams `
    $Entry

$PackageDir = Join-Path $Dist "restaurant_bot"
$DebugLauncher = Join-Path $PackageDir "debug-ui.bat"
Set-Content -LiteralPath $DebugLauncher -Encoding ASCII -Value @(
    "@echo off",
    'start "" "%~dp0restaurant_bot.exe" --debug-ui'
)

Write-Host "Package created:"
Write-Host $PackageDir
Write-Host "Normal: restaurant_bot.exe"
Write-Host "Debug : debug-ui.bat"

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Entry = Join-Path $Root "tools\restaurant_bot.py"
$Dist = Join-Path $Root "dist\restaurant_bot_build"
$Release = Join-Path $Root "dist\restaurant_bot_for_users"
$Work = Join-Path $Root "build\restaurant_bot"
$Spec = Join-Path $Root "build"
$Readme = Join-Path $Root "docs\restaurant_bot_readme.txt"

if (-not (Test-Path $Entry)) {
    throw "Entry file not found: $Entry"
}

if (Test-Path $Dist) {
    Remove-Item -LiteralPath $Dist -Recurse -Force
}
if (Test-Path $Release) {
    Remove-Item -LiteralPath $Release -Recurse -Force
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
$AppDir = Join-Path $Release "app"
New-Item -ItemType Directory -Path $Release | Out-Null
Copy-Item -LiteralPath $PackageDir -Destination $AppDir -Recurse

Set-Content -LiteralPath (Join-Path $Release "Start.bat") -Encoding ASCII -Value @(
    "@echo off",
    'start "" "%~dp0app\restaurant_bot.exe"'
)
Set-Content -LiteralPath (Join-Path $Release "Debug.bat") -Encoding ASCII -Value @(
    "@echo off",
    'start "" "%~dp0app\restaurant_bot.exe" --debug-ui'
)

if (Test-Path $Readme) {
    Copy-Item -LiteralPath $Readme -Destination (Join-Path $Release "README.txt")
}

Write-Host "Package created:"
Write-Host $Release
Write-Host "Give users the whole restaurant_bot_for_users folder."
Write-Host "Normal: Start.bat"
Write-Host "Debug : Debug.bat"

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ConfigDir = Join-Path $ProjectRoot 'config'
$ExportDir = Join-Path $ConfigDir 'exports'
$ManageUsersScript = Join-Path $PSScriptRoot 'manage_irl_users.ps1'

function Confirm-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host $Message -ForegroundColor Yellow
    $answer = (Read-Host '輸入 y 繼續，其他按鍵取消').Trim().ToLower()
    return ($answer -eq 'y')
}

function Copy-IfExists {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (Test-Path -LiteralPath $Source) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return $true
    }

    return $false
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '      產生筆電 IRL 搬移包     ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '這個搬移包會包含 Dynu、IRL 白名單、台主推流 / 拉流密鑰。' -ForegroundColor Yellow
Write-Host '請只放在自己的電腦或隨身碟，不要上傳公開網路。' -ForegroundColor Yellow

if (-not (Confirm-Step '是否產生給 LAPTOP-6N12C053 使用的搬移包？')) {
    Write-Host '已取消。' -ForegroundColor DarkGray
    exit 0
}

if (Test-Path -LiteralPath $ManageUsersScript) {
    try {
        & $ManageUsersScript -Mode Apply
    } catch {
        Write-Host "套用白名單時發生錯誤：$($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host '仍會繼續打包現有設定檔。' -ForegroundColor DarkGray
    }
}

New-Item -ItemType Directory -Path $ExportDir -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$zipPath = Join-Path $ExportDir "irl-laptop-transfer-$timestamp.zip"
$tempRoot = Join-Path $env:TEMP "irl-laptop-transfer-$([Guid]::NewGuid().ToString('N'))"
$tempConfig = Join-Path $tempRoot 'config'

try {
    New-Item -ItemType Directory -Path $tempConfig -Force | Out-Null

    $copied = New-Object System.Collections.Generic.List[string]
    $files = @(
        'dynu_ddns.json',
        'relay_settings.json',
        'relay_users.json',
        'mediamtx.yml'
    )

    foreach ($file in $files) {
        $source = Join-Path $ConfigDir $file
        $dest = Join-Path $tempConfig $file
        if (Copy-IfExists -Source $source -Destination $dest) {
            $copied.Add("config/$file")
        }
    }

    $readme = @"
IRL 筆電搬移包
================

目標筆電：LAPTOP-6N12C053

這個 zip 內含 Dynu DDNS、IRL 白名單、MediaMTX 實際設定與台主密鑰。
請不要公開上傳，也不要貼到 Discord / 聊天室。

使用方式：
1. 在筆電準備好 projects/irl-stream 專案資料夾。
2. 把這個 zip 放到筆電。
3. 在筆電雙擊 launchers/初始化筆電IRL環境.bat。
4. 腳本詢問搬移包路徑時，貼上這個 zip 的完整路徑。

打包時間：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
"@
    [System.IO.File]::WriteAllText((Join-Path $tempRoot 'README-筆電搬移.txt'), $readme, [System.Text.UTF8Encoding]::new($true))

    if ($copied.Count -eq 0) {
        Write-Host '找不到可搬移的私有設定檔，沒有產生 zip。' -ForegroundColor Red
        exit 1
    }

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -Force

    Write-Host ''
    Write-Host '搬移包已產生：' -ForegroundColor Green
    Write-Host "  $zipPath" -ForegroundColor Cyan
    Write-Host ''
    Write-Host '包含檔案：' -ForegroundColor Cyan
    foreach ($item in $copied) {
        Write-Host "  $item"
    }
    Write-Host ''
    Write-Host '下一步：把這個 zip 帶到筆電，執行「初始化筆電IRL環境.bat」。' -ForegroundColor Yellow
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

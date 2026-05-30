[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ConfigDir   = Join-Path $ProjectRoot 'config'
$ExportDir   = Join-Path $ConfigDir 'exports'
$ManageUsersScript = Join-Path $PSScriptRoot 'manage_irl_users.ps1'

function Confirm-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host $Message -ForegroundColor Yellow
    $rawAnswer = Read-Host '輸入 y 繼續，其他按鍵取消'
    $answer = if ($null -eq $rawAnswer) { '' } else { $rawAnswer.Trim().ToLower() }
    return ($answer -eq 'y')
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '      產生筆電 IRL 搬移包     ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '搬移包包含：所有 IRL 腳本與啟動檔、Dynu、白名單、密鑰設定。' -ForegroundColor Yellow
Write-Host '請只放在自己的電腦或隨身碟，不要上傳公開網路。' -ForegroundColor Yellow

if (-not (Confirm-Step '是否產生給 LAPTOP-6N12C053 使用的完整搬移包？')) {
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
$zipPath  = Join-Path $ExportDir "irl-laptop-$timestamp.zip"
$tempRoot = Join-Path $env:TEMP "irl-laptop-$([Guid]::NewGuid().ToString('N'))"

try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    # ── 公開檔案：launchers、scripts、tools ──────────────────────────
    $publicDirs = @('launchers', 'scripts', 'tools')
    foreach ($dir in $publicDirs) {
        $src = Join-Path $ProjectRoot $dir
        $dst = Join-Path $tempRoot $dir
        if (Test-Path -LiteralPath $src) {
            Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
        }
    }

    # ── 私有設定：config ─────────────────────────────────────────────
    $configFiles = @('dynu_ddns.json','relay_settings.json','relay_users.json','mediamtx.yml')
    $tempConfig  = Join-Path $tempRoot 'config'
    $copiedConfig = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $configFiles) {
        $src = Join-Path $ConfigDir $file
        if (Test-Path -LiteralPath $src) {
            New-Item -ItemType Directory -Path $tempConfig -Force | Out-Null
            Copy-Item -LiteralPath $src -Destination (Join-Path $tempConfig $file) -Force
            $copiedConfig.Add("config\$file")
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $tempRoot 'launchers'))) {
        throw '找不到 launchers 資料夾，請確認從正確位置執行。'
    }

    # ── README ───────────────────────────────────────────────────────
    $readme = @"
IRL 筆電完整搬移包
==================

目標筆電：LAPTOP-6N12C053
打包時間：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

使用方式：
1. 把這個 zip 複製到筆電。
2. 解壓縮到目標資料夾（例如 D:\下載\BOTS\直播中繼）。
3. 雙擊 launchers\初始化筆電IRL環境.bat。
4. 腳本詢問搬移包路徑時，直接按 Enter（config 已在資料夾內）。
5. 依提示完成防火牆設定。

注意：zip 內含台主密鑰，請勿上傳公開網路。
"@
    [System.IO.File]::WriteAllText(
        (Join-Path $tempRoot 'README-筆電搬移.txt'),
        $readme,
        [System.Text.UTF8Encoding]::new($true)
    )

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -Force

    Write-Host ''
    Write-Host '搬移包已產生：' -ForegroundColor Green
    Write-Host "  $zipPath" -ForegroundColor Cyan
    Write-Host ''
    if ($copiedConfig.Count -gt 0) {
        Write-Host '包含私有設定：' -ForegroundColor Cyan
        foreach ($item in $copiedConfig) { Write-Host "  $item" }
    } else {
        Write-Host '注意：找不到私有設定檔（config 資料夾為空），請手動補上或在 LAPTOP 初始化時輸入路徑。' -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host '下一步：把 zip 複製到筆電，解壓後雙擊 launchers\初始化筆電IRL環境.bat。' -ForegroundColor Yellow
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

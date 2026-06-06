$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ExportDir   = Join-Path $ProjectRoot 'config\exports'

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
Write-Host '     產生筆電程式更新包      ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '更新包只含程式碼（scripts / launchers）。' -ForegroundColor Yellow
Write-Host '不含 config（白名單、密鑰、Dynu、通知設定），筆電解壓後不會覆蓋這些。' -ForegroundColor Yellow
Write-Host '也不含 tools（mediamtx.exe 等）。' -ForegroundColor Yellow

if (-not (Confirm-Step '是否產生筆電程式更新包？')) {
    Write-Host '已取消。' -ForegroundColor DarkGray
    exit 0
}

New-Item -ItemType Directory -Path $ExportDir -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$zipPath  = Join-Path $ExportDir "irl-laptop-code-$timestamp.zip"
$tempRoot = Join-Path $env:TEMP "irl-laptop-code-$([Guid]::NewGuid().ToString('N'))"

try {
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    # ── launchers（排除桌電端工具）──────────────────────────────────
    $launcherExclude = @('install_noalbs.bat', '啟動BRB伺服器.bat', '產生筆電程式更新包.bat', '啟動桌電環境.bat', '關閉桌電環境.bat')
    $dstLaunchers = Join-Path $tempRoot 'launchers'
    New-Item -ItemType Directory -Path $dstLaunchers -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'launchers') -File |
        Where-Object { $launcherExclude -notcontains $_.Name } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dstLaunchers -Force }

    # ── scripts（排除桌電端工具）────────────────────────────────────
    $scriptExclude = @('install_noalbs_core.ps1', 'brb_server.ps1', 'export_laptop_code_update.ps1', 'start_desktop.ps1', 'stop_desktop.ps1')
    $dstScripts = Join-Path $tempRoot 'scripts'
    New-Item -ItemType Directory -Path $dstScripts -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'scripts') -File |
        Where-Object { $scriptExclude -notcontains $_.Name } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dstScripts -Force }

    if (-not (Test-Path -LiteralPath (Join-Path $tempRoot 'launchers'))) {
        throw '找不到 launchers 資料夾，請確認從正確位置執行。'
    }

    # ── README ───────────────────────────────────────────────────────
    $readme = @"
IRL 筆電程式更新包
==================

目標筆電：LAPTOP-6N12C053
打包時間：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

內容：只有程式碼（scripts / launchers）。
不含 config（白名單、密鑰、Dynu、通知設定），也不含 tools（mediamtx.exe 等）。

使用方式：
1. 把這個 zip 複製到筆電。
2. 解壓縮，直接覆蓋筆電現有的 IRL 資料夾。
3. 只會更新 scripts 和 launchers，config 與 tools 原封不動。
4. 不需要再跑初始化；覆蓋完程式就是最新的。

第一次更新後，若筆電還沒設過管理員通知，雙擊 launchers\設定管理員通知.bat 設定一次即可。

注意：白名單與密鑰一律保留在筆電，不在這個更新包裡。
"@
    [System.IO.File]::WriteAllText(
        (Join-Path $tempRoot 'README-筆電更新.txt'),
        $readme,
        [System.Text.UTF8Encoding]::new($true)
    )

    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -Force

    Write-Host ''
    Write-Host '程式更新包已產生：' -ForegroundColor Green
    Write-Host "  $zipPath" -ForegroundColor Cyan
    Write-Host ''
    Write-Host '下一步：把 zip 複製到筆電，解壓覆蓋現有 IRL 資料夾即可。' -ForegroundColor Yellow
    Write-Host 'config（白名單/密鑰）與 tools 不會被動到。' -ForegroundColor Yellow
} finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

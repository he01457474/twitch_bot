$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvFile = Join-Path $ProjectRoot '.env'

function Read-Required {
    param([string]$Prompt)
    do {
        $value = Read-Host $Prompt
        $value = if ($null -eq $value) { '' } else { $value.Trim() }
        if (-not $value) { Write-Host '這個欄位不能空白。' -ForegroundColor Red }
    } while (-not $value)
    return $value
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '     設定 Discord 指令監聽    ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '設定後，在 Discord 打 /狀態 就能查 IRL 中繼狀態。' -ForegroundColor Yellow
Write-Host '需要一個 Discord bot token，申請步驟：' -ForegroundColor Yellow
Write-Host '  1. 進 Discord Developer Portal → New Application' -ForegroundColor DarkGray
Write-Host '  2. 左邊 Bot → Reset Token → 複製 Token' -ForegroundColor DarkGray
Write-Host '  3. OAuth2 → URL Generator → 勾 bot 和 applications.commands' -ForegroundColor DarkGray
Write-Host '     → 用產生的網址把 bot 邀請進你的伺服器' -ForegroundColor DarkGray
Write-Host '  （slash 指令不需要開 MESSAGE CONTENT INTENT）' -ForegroundColor DarkGray
Write-Host '  4. 筆電要先 pip install discord.py python-dotenv' -ForegroundColor DarkGray
Write-Host ''

$token = Read-Required 'Discord Bot Token'

$guildId = Read-Host '主伺服器 ID（只在這個伺服器生效；Enter 表示不限）'
$guildId = if ($null -eq $guildId) { '' } else { $guildId.Trim() }

$pythonPath = Read-Host 'Python 執行檔路徑（Enter 用系統 pythonw；建議填筆電的 python 完整路徑）'
$pythonPath = if ($null -eq $pythonPath) { '' } else { $pythonPath.Trim('" ') }

# 讀現有 .env，移除舊的 IRL_* 鍵後重寫，保留其他設定
$lines = @()
if (Test-Path -LiteralPath $EnvFile) {
    $lines = @(Get-Content -LiteralPath $EnvFile -Encoding UTF8)
}
$keys = @('IRL_DISCORD_TOKEN', 'IRL_MAIN_GUILD_ID', 'IRL_PYTHON_PATH')
$kept = foreach ($line in $lines) {
    $skip = $false
    foreach ($k in $keys) { if ($line -match "^\s*$k\s*=") { $skip = $true; break } }
    if (-not $skip) { $line }
}

$new = @($kept)
$new += "IRL_DISCORD_TOKEN=$token"
if ($guildId)   { $new += "IRL_MAIN_GUILD_ID=$guildId" }
if ($pythonPath) { $new += "IRL_PYTHON_PATH=$pythonPath" }

[System.IO.File]::WriteAllText($EnvFile, (($new -join "`r`n") + "`r`n"), [System.Text.UTF8Encoding]::new($false))

Write-Host ''
Write-Host "設定已儲存：$EnvFile" -ForegroundColor Green
Write-Host '下次雙擊「啟動直播環境」時，Discord 指令監聽會自動在背景跑。' -ForegroundColor Cyan
Write-Host '提醒：筆電要先安裝 discord.py 與 python-dotenv 才跑得起來。' -ForegroundColor Yellow
Write-Host '另外，狀態是透過管理員通知 webhook 貼出，請確認已用「設定管理員通知.bat」設定過。' -ForegroundColor Yellow
Read-Host '按 Enter 關閉'

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir = Get-IrlConfigDir
$DynuConfig = Join-Path $ConfigDir 'dynu_ddns.json'
$UpdaterScript = Join-Path $PSScriptRoot 'update_dynu_ddns.ps1'
$TaskName = 'FlyCat IRL Dynu DDNS Update'

function Read-Required {
    param([string]$Prompt)
    do {
        $value = (Read-Host $Prompt).Trim()
        if (-not $value) { Write-Host '這個欄位不能空白。' -ForegroundColor Red }
    } while (-not $value)
    return $value
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '        設定 Dynu DDNS        ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '請先在 Dynu 建好 hostname，例如 flycat.dynu.net。' -ForegroundColor Yellow
Write-Host '密碼建議使用 Dynu 的 IP update password，不要使用你主要登入密碼。' -ForegroundColor Yellow
Write-Host ''

$hostname = (Read-Required 'Dynu hostname（例如 flycat.dynu.net）').ToLower()
$username = Read-Required 'Dynu username'
$securePassword = Read-Host 'Dynu IP update password' -AsSecureString

New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
$config = [pscustomobject]@{
    provider = 'Dynu'
    hostname = $hostname
    username = $username
    password = ($securePassword | ConvertFrom-SecureString)
    updatedAt = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
}
$json = $config | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($DynuConfig, $json, [System.Text.UTF8Encoding]::new($false))
Set-IrlRelayHost -RelayHost $hostname -Provider 'Dynu'

Write-Host ''
Write-Host '正在測試 Dynu 更新...' -ForegroundColor Cyan
& $UpdaterScript

Write-Host ''
Write-Host '建立 Windows 排程，每 5 分鐘自動更新 Dynu DDNS...' -ForegroundColor Cyan
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$UpdaterScript`""
$startTime = (Get-Date).AddMinutes(1).ToString('HH:mm')
$result = & schtasks.exe /Create /TN $TaskName /TR $taskCommand /SC MINUTE /MO 5 /ST $startTime /F 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host 'Dynu 自動更新排程已建立。' -ForegroundColor Green
} else {
    Write-Host '建立排程失敗，請用系統管理員身分重跑，或先手動執行「更新DynuDDNS.bat」。' -ForegroundColor Yellow
    Write-Host ($result | Out-String).Trim() -ForegroundColor DarkGray
}

Write-Host ''
Write-Host "目前 IRL 對外網址已設定為：$hostname" -ForegroundColor Green
Write-Host '後續台主拿到的新設定會使用這個 Dynu hostname。' -ForegroundColor Yellow
Read-Host '按 Enter 關閉'

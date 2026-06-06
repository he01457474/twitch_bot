$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir = Get-IrlConfigDir
$UsersFile = Join-Path $ConfigDir 'relay_users.json'
$DynuFile  = Join-Path $ConfigDir 'dynu_ddns.json'

function Write-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host "== $Title ==" -ForegroundColor Cyan
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '        IRL 中繼狀態         ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host "電腦：$env:COMPUTERNAME（請在跑中繼的筆電上查最準）" -ForegroundColor DarkGray

# ── 1. MediaMTX 程序 ────────────────────────────────────────────────
Write-Section 'MediaMTX 伺服器'
$proc = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host ("執行中（PID {0}）" -f (($proc | ForEach-Object { $_.Id }) -join ', ')) -ForegroundColor Green
} else {
    Write-Host '沒有在執行' -ForegroundColor Red
}

# ── 讀白名單 ────────────────────────────────────────────────────────
$users = $null
if (Test-Path -LiteralPath $UsersFile) {
    try { $users = Get-Content -LiteralPath $UsersFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
}

# ── 查 MediaMTX API 即時路徑 ────────────────────────────────────────
$activePaths = @{}
$apiOk = $false
try {
    $resp = Invoke-RestMethod -Uri 'http://localhost:9997/v3/paths/list' -UseBasicParsing -TimeoutSec 5
    $apiOk = $true
    foreach ($item in @($resp.items)) {
        $name = [string]$item.name
        if (-not $name) { continue }
        $ready = $false
        if ($item.PSObject.Properties['sourceReady']) { $ready = [bool]$item.sourceReady }
        elseif ($item.PSObject.Properties['source'] -and $item.source) { $ready = $true }
        $activePaths[$name] = $ready
    }
} catch {}

# ── 2. 目前推流狀態 ─────────────────────────────────────────────────
Write-Section '目前推流狀態'
if (-not $apiOk) {
    Write-Host 'MediaMTX API（9997）連不上，可能伺服器沒開或還沒就緒。' -ForegroundColor Yellow
} else {
    $online = @($activePaths.GetEnumerator() | Where-Object { $_.Value } | ForEach-Object { $_.Key })
    if ($online.Count -gt 0) {
        foreach ($id in $online) { Write-Host "推流中：$id" -ForegroundColor Green }
    } else {
        Write-Host '目前沒有台主在推流。' -ForegroundColor DarkGray
    }
}

# ── 3. 白名單台主 ───────────────────────────────────────────────────
Write-Section '白名單台主'
if (-not $users -or -not $users.users) {
    Write-Host '尚無白名單資料。' -ForegroundColor Yellow
} else {
    foreach ($prop in $users.users.PSObject.Properties) {
        $id = $prop.Name
        $enabled = [bool]$prop.Value.enabled
        $statusLabel = if ($enabled) { '啟用' } else { '停用' }
        $color = if ($enabled) { 'Green' } else { 'DarkGray' }
        $live = if ($activePaths.ContainsKey($id) -and $activePaths[$id]) { '  ◀ 推流中' } else { '' }
        Write-Host ("{0}  [{1}]{2}" -f $id, $statusLabel, $live) -ForegroundColor $color
    }
}

# ── 4. Dynu DDNS ────────────────────────────────────────────────────
Write-Section 'Dynu DDNS'
if (-not (Test-Path -LiteralPath $DynuFile)) {
    Write-Host '尚未設定 Dynu DDNS。' -ForegroundColor Yellow
} else {
    $dynu = $null
    try { $dynu = Get-Content -LiteralPath $DynuFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    if ($dynu) {
        $hostname = [string]$dynu.hostname
        Write-Host "對外網域：$hostname"
        if ($dynu.updatedAt) { Write-Host "設定更新時間：$($dynu.updatedAt)" -ForegroundColor DarkGray }

        $resolved = ''
        try {
            $resolved = (Resolve-DnsName -Name $hostname -Type A -ErrorAction Stop |
                Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress
            if ($resolved) { Write-Host "網域目前指向：$resolved" -ForegroundColor Green }
        } catch {
            Write-Host '無法解析網域目前的 IP。' -ForegroundColor Yellow
        }

        try {
            $wanIp = Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 5
            if ($wanIp) {
                Write-Host "這台目前對外 IP：$wanIp"
                if ($resolved -and $wanIp -eq $resolved) {
                    Write-Host '✔ 網域 IP 與目前對外 IP 一致。' -ForegroundColor Green
                } elseif ($resolved -and $wanIp -ne $resolved) {
                    Write-Host '⚠ 網域指向的 IP 跟目前對外 IP 不一致，DDNS 可能還沒更新。' -ForegroundColor Yellow
                }
            }
        } catch {}
    }
}

Write-Host ''
Read-Host '按 Enter 關閉'

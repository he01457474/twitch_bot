param(
    [switch]$ToDiscord
)

$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir = Get-IrlConfigDir
$UsersFile = Join-Path $ConfigDir 'relay_users.json'
$DynuFile  = Join-Path $ConfigDir 'dynu_ddns.json'
$NotifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'

# 同時印到畫面、收集成純文字（給 Discord 用）
$report = [System.Collections.Generic.List[string]]::new()

function Emit {
    param([string]$Text, [string]$Color = 'Gray', [switch]$NoReport)
    Write-Host $Text -ForegroundColor $Color
    if (-not $NoReport) { $report.Add($Text) }
}

function Emit-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host "== $Title ==" -ForegroundColor Cyan
    $report.Add('')
    $report.Add("【$Title】")
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '        IRL 中繼狀態         ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host "電腦：$env:COMPUTERNAME（請在跑中繼的筆電上查最準）" -ForegroundColor DarkGray

# ── 1. MediaMTX 程序 ────────────────────────────────────────────────
Emit-Section 'MediaMTX 伺服器'
$proc = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
if ($proc) {
    Emit ("執行中（PID {0}）" -f (($proc | ForEach-Object { $_.Id }) -join ', ')) 'Green'
} else {
    Emit '沒有在執行' 'Red'
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
Emit-Section '目前推流狀態'
if (-not $apiOk) {
    Emit 'MediaMTX API（9997）連不上，可能伺服器沒開或還沒就緒。' 'Yellow'
} else {
    $online = @($activePaths.GetEnumerator() | Where-Object { $_.Value } | ForEach-Object { $_.Key })
    if ($online.Count -gt 0) {
        foreach ($id in $online) { Emit "推流中：$id" 'Green' }
    } else {
        Emit '目前沒有台主在推流。' 'DarkGray'
    }
}

# ── 3. 白名單台主 ───────────────────────────────────────────────────
Emit-Section '白名單台主'
if (-not $users -or -not $users.users) {
    Emit '尚無白名單資料。' 'Yellow'
} else {
    foreach ($prop in $users.users.PSObject.Properties) {
        $id = $prop.Name
        $enabled = [bool]$prop.Value.enabled
        $statusLabel = if ($enabled) { '啟用' } else { '停用' }
        $color = if ($enabled) { 'Green' } else { 'DarkGray' }
        $live = if ($activePaths.ContainsKey($id) -and $activePaths[$id]) { '  ◀ 推流中' } else { '' }
        Emit ("{0}  [{1}]{2}" -f $id, $statusLabel, $live) $color
    }
}

# ── 4. Dynu DDNS ────────────────────────────────────────────────────
Emit-Section 'Dynu DDNS'
if (-not (Test-Path -LiteralPath $DynuFile)) {
    Emit '尚未設定 Dynu DDNS。' 'Yellow'
} else {
    $dynu = $null
    try { $dynu = Get-Content -LiteralPath $DynuFile -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    if ($dynu) {
        $hostname = [string]$dynu.hostname
        Emit "對外網域：$hostname"
        if ($dynu.updatedAt) { Emit "設定更新時間：$($dynu.updatedAt)" 'DarkGray' }

        $resolved = ''
        try {
            $resolved = (Resolve-DnsName -Name $hostname -Type A -ErrorAction Stop |
                Where-Object { $_.IPAddress } | Select-Object -First 1).IPAddress
            if ($resolved) { Emit "網域目前指向：$resolved" 'Green' }
        } catch {
            Emit '無法解析網域目前的 IP。' 'Yellow'
        }

        try {
            $wanIp = Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 5
            if ($wanIp) {
                Emit "這台目前對外 IP：$wanIp"
                if ($resolved -and $wanIp -eq $resolved) {
                    Emit '網域 IP 與目前對外 IP 一致。' 'Green'
                } elseif ($resolved -and $wanIp -ne $resolved) {
                    Emit '網域指向的 IP 跟目前對外 IP 不一致，DDNS 可能還沒更新。' 'Yellow'
                }
            }
        } catch {}
    }
}

# ── 發到 Discord ────────────────────────────────────────────────────
if ($ToDiscord) {
    Write-Host ''
    if (Test-Path -LiteralPath $NotifyScript) {
        & $NotifyScript -Title 'IRL 中繼狀態查詢' -Message ($report -join "`n") -Level Info -Key 'irl-status-query' -CooldownMinutes 0
        Write-Host '已送出到 Discord（若沒收到，請先用「設定管理員通知.bat」設定 webhook）。' -ForegroundColor Green
    } else {
        Write-Host "找不到通知腳本：$NotifyScript" -ForegroundColor Red
    }
}

# 被自動呼叫（-ToDiscord）時不卡住等待，方便排程；人工查看才停留
if (-not $ToDiscord) {
    Write-Host ''
    Read-Host '按 Enter 關閉'
}

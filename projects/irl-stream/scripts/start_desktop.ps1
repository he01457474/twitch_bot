[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir     = Get-IrlConfigDir
$BrbScript     = Join-Path $PSScriptRoot 'brb_server.ps1'
$DesktopConfig = Join-Path $ConfigDir 'desktop_settings.json'
$BrbPidFile    = "$env:TEMP\brb_server.pid"

function Load-DesktopConfig {
    if (Test-Path -LiteralPath $DesktopConfig) {
        try { return Get-Content $DesktopConfig -Raw -Encoding UTF8 | ConvertFrom-Json }
        catch {}
    }
    return [pscustomobject]@{ noalbsExe = ''; laptopLocalIp = '' }
}

function Get-LaptopIp {
    param([pscustomobject]$Cfg)
    if ($Cfg.laptopLocalIp -and $Cfg.laptopLocalIp -ne '') { return $Cfg.laptopLocalIp }
    Write-Host ''
    Write-Host '尚未設定筆電內網 IP。' -ForegroundColor Yellow
    Write-Host '請到筆電跑 ipconfig，找「IPv4 位址」那行（通常是 192.168.x.x）。' -ForegroundColor DarkGray
    $ip = (Read-Host '請輸入筆電內網 IP').Trim()
    return $ip
}

function Test-RelayOnline {
    param([string]$Ip)
    try {
        Invoke-WebRequest -Uri "http://${Ip}:9997/v3/config/global/get" `
            -UseBasicParsing -TimeoutSec 5 | Out-Null
        return $true
    } catch { return $false }
}

function Save-DesktopConfig {
    param([pscustomobject]$Config)
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    $Config | ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $DesktopConfig -Encoding UTF8
}

function Find-NoalbsExe {
    param([string]$SavedPath)
    if ($SavedPath -and (Test-Path -LiteralPath $SavedPath)) { return $SavedPath }

    $roots = @(
        $env:USERPROFILE,
        (Join-Path $env:USERPROFILE 'Desktop'),
        (Join-Path $env:USERPROFILE 'Downloads'),
        (Join-Path $env:USERPROFILE 'Documents')
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        $hit = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -imatch 'noalbs' } |
            ForEach-Object { Join-Path $_.FullName 'noalbs.exe' } |
            Where-Object { Test-Path $_ } |
            Select-Object -First 1
        if ($hit) { return $hit }
    }
    return ''
}

function Start-BrbServer {
    Write-Host '[2/3] BRB 伺服器...'
    if (-not (Test-Path -LiteralPath $BrbScript)) {
        Write-Host '  找不到 brb_server.ps1，跳過。' -ForegroundColor DarkGray
        return
    }

    if (Test-Path $BrbPidFile) {
        $oldPid = Get-Content $BrbPidFile -ErrorAction SilentlyContinue
        if ($oldPid -and (Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue)) {
            Write-Host '  BRB 伺服器已在執行' -ForegroundColor Green
            return
        }
        Remove-Item $BrbPidFile -ErrorAction SilentlyContinue
    }

    $proc = Start-Process powershell `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$BrbScript`"" `
        -WindowStyle Hidden -PassThru
    $proc.Id | Set-Content $BrbPidFile
    Write-Host '  BRB 伺服器已啟動（http://localhost:8080）' -ForegroundColor Green
}

function Update-NoalbsStatsUrl {
    param([string]$Exe, [string]$Ip)
    if (-not $Exe) { return }
    $cfgPath = Join-Path (Split-Path $Exe) 'config.json'
    if (-not (Test-Path -LiteralPath $cfgPath)) { return }
    try {
        $cfg     = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $changed = $false
        foreach ($srv in $cfg.switcher.streamServers) {
            $url = $srv.streamServer.statsUrl
            if ($url -match '^http://[^:]+:') {
                $newUrl = $url -replace '^http://[^:]+:', "http://${Ip}:"
                if ($url -ne $newUrl) {
                    $srv.streamServer.statsUrl = $newUrl
                    $changed = $true
                }
            }
        }
        if ($changed) {
            $cfg | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $cfgPath -Encoding UTF8
            Write-Host "  已更新 NOALBS statsUrl → $Ip" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  無法更新 NOALBS 設定：$($_.Exception.Message)" -ForegroundColor DarkGray
    }
}

function Start-ExitWatcher {
    param([int]$NoalbsPid)
    $cmd = @"
`$p = Get-Process -Id $NoalbsPid -ErrorAction SilentlyContinue
if (`$p) { `$p.WaitForExit() }
`$wsh = New-Object -ComObject WScript.Shell
`$wsh.Popup('NOALBS 已關閉，直播環境仍在執行中。`n記得雙擊「關閉桌電環境.bat」關閉 BRB 伺服器。', 0, '直播結束提醒', 64) | Out-Null
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
    Start-Process powershell -WindowStyle Hidden `
        -ArgumentList "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"
}

function Start-NoalbsProcess {
    param([pscustomobject]$Cfg)
    Write-Host '[3/3] NOALBS...'
    $exe = Find-NoalbsExe $Cfg.noalbsExe

    if (-not $exe) {
        Write-Host '  找不到 NOALBS。' -ForegroundColor Yellow
        $rawPath = (Read-Host '  請輸入 noalbs.exe 完整路徑（Enter 跳過）').Trim('"').Trim()
        if (-not $rawPath -or -not (Test-Path -LiteralPath $rawPath)) {
            Write-Host '  跳過 NOALBS。' -ForegroundColor DarkGray
            return
        }
        $exe = $rawPath
    }

    $Cfg.noalbsExe = $exe
    Save-DesktopConfig $Cfg

    Update-NoalbsStatsUrl $exe $Cfg.laptopLocalIp

    $existing = Get-Process 'noalbs' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) {
        Write-Host '  NOALBS 已在執行' -ForegroundColor Green
        Start-ExitWatcher $existing.Id
        return
    }

    $proc = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe) -PassThru
    Start-ExitWatcher $proc.Id
    Write-Host '  NOALBS 已啟動' -ForegroundColor Green
    Write-Host '  若聊天室指令無回應，請確認 .env 裡的 TWITCH_BOT_OAUTH 是否過期。' -ForegroundColor DarkGray
}

# ── 主流程 ────────────────────────────────────────────────────────

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '      桌電開台環境啟動       ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''

$cfg      = Load-DesktopConfig
$laptopIp = Get-LaptopIp $cfg
$cfg.laptopLocalIp = $laptopIp
Save-DesktopConfig $cfg

Write-Host '[1/3] 確認中繼伺服器...'
if (Test-RelayOnline $laptopIp) {
    Write-Host "  中繼伺服器已上線（$laptopIp）" -ForegroundColor Green
} else {
    Write-Host "  中繼伺服器無回應（$laptopIp）" -ForegroundColor Red
    Write-Host '  請先在筆電雙擊「啟動直播環境.bat」。' -ForegroundColor Yellow
    Write-Host ''
    $ans = (Read-Host '  仍要繼續啟動桌電環境？（y/n）').Trim().ToLower()
    if ($ans -ne 'y') { exit 0 }
}

Start-BrbServer
Start-NoalbsProcess $cfg

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '       桌電環境已就緒        ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host '接下來：' -ForegroundColor Yellow
Write-Host '1. 開 OBS'
Write-Host '2. 手機開始推流'
Write-Host '3. Twitch 聊天室輸入 !start'
Write-Host ''
Write-Host "BRB 網頁：http://localhost:8080" -ForegroundColor Cyan
Write-Host "串流狀態：http://${laptopIp}:9997/v3/paths/list" -ForegroundColor Cyan
Write-Host ''
Read-Host '按 Enter 關閉'

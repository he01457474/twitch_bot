param(
    [string]$ImportZip = ''
)

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ExpectedComputerName = 'LAPTOP-6N12C053'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ConfigDir = Join-Path $ProjectRoot 'config'
$MediaMtxDir = Join-Path $ProjectRoot 'tools\mediamtx'
$MediaMtxExe = Join-Path $MediaMtxDir 'mediamtx.exe'
$ManageUsersScript = Join-Path $PSScriptRoot 'manage_irl_users.ps1'
$StartLauncher = Join-Path $ProjectRoot 'launchers\啟動直播環境.bat'
$DynuLauncher = Join-Path $ProjectRoot 'launchers\設定DynuDDNS.bat'
$UsersLauncher = Join-Path $ProjectRoot 'launchers\管理IRL白名單.bat'

function Confirm-Step {
    param([string]$Message)
    Write-Host ''
    Write-Host $Message -ForegroundColor Yellow
    $answer = (Read-Host '輸入 y 繼續，其他按鍵跳過').Trim().ToLower()
    return ($answer -eq 'y')
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PrimaryIPv4 {
    try {
        $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
            Sort-Object RouteMetric, InterfaceMetric |
            Select-Object -First 1
        if ($route) {
            $ip = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.ifIndex -ErrorAction Stop |
                Where-Object { $_.IPAddress -notlike '169.254.*' } |
                Select-Object -First 1
            if ($ip) { return [string]$ip.IPAddress }
        }
    } catch {
    }

    try {
        $ip = Get-NetIPConfiguration |
            Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
            Select-Object -First 1
        if ($ip) { return [string]$ip.IPv4Address.IPAddress }
    } catch {
    }

    return ''
}

function Import-PrivateConfig {
    param([string]$ZipPath)

    if (-not $ZipPath) { return }
    if (-not (Test-Path -LiteralPath $ZipPath)) {
        Write-Host "找不到搬移包：$ZipPath" -ForegroundColor Red
        return
    }

    if (-not (Confirm-Step "即將把搬移包匯入到：$ConfigDir`n這會建立或覆蓋 Dynu / 白名單 / MediaMTX 私有設定。")) {
        Write-Host '已跳過匯入搬移包。' -ForegroundColor DarkGray
        return
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null

    $allowed = @(
        'config/dynu_ddns.json',
        'config/relay_settings.json',
        'config/relay_users.json',
        'config/mediamtx.yml'
    )

    $archive = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path -LiteralPath $ZipPath).Path)
    try {
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if ($allowed -notcontains $name) { continue }
            $fileName = Split-Path $name -Leaf
            $dest = Join-Path $ConfigDir $fileName
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $true)
            Write-Host "已匯入：$fileName" -ForegroundColor Green
        }
    } finally {
        $archive.Dispose()
    }
}

function Install-MediaMtx {
    if (Test-Path -LiteralPath $MediaMtxExe) {
        Write-Host "MediaMTX 已存在：$MediaMtxExe" -ForegroundColor Green
        return
    }

    if (-not (Confirm-Step "找不到 MediaMTX。是否從 GitHub 下載 Windows 版 MediaMTX 到：$MediaMtxDir？")) {
        Write-Host '已跳過下載 MediaMTX。' -ForegroundColor DarkGray
        return
    }

    New-Item -ItemType Directory -Path $MediaMtxDir -Force | Out-Null
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/bluenviron/mediamtx/releases/latest' -Headers @{ 'User-Agent' = 'FlyCatIRLSetup' } -TimeoutSec 30
    $asset = $release.assets |
        Where-Object { $_.name -match 'windows_amd64.*\.zip$' } |
        Select-Object -First 1

    if (-not $asset) {
        throw '找不到 MediaMTX Windows amd64 zip，請改手動下載。'
    }

    $tempDir = Join-Path $env:TEMP "mediamtx-$([Guid]::NewGuid().ToString('N'))"
    $zipPath = Join-Path $tempDir $asset.name
    try {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        Write-Host "正在下載：$($asset.browser_download_url)" -ForegroundColor Cyan
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing -TimeoutSec 120
        Expand-Archive -LiteralPath $zipPath -DestinationPath $tempDir -Force

        $exe = Get-ChildItem -LiteralPath $tempDir -Recurse -Filter 'mediamtx.exe' | Select-Object -First 1
        if (-not $exe) { throw '下載檔案中找不到 mediamtx.exe。' }

        $sourceDir = $exe.Directory.FullName
        Get-ChildItem -LiteralPath $sourceDir -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $MediaMtxDir -Recurse -Force
        }

        Write-Host "MediaMTX 已安裝到：$MediaMtxDir" -ForegroundColor Green
    } finally {
        if (Test-Path -LiteralPath $tempDir) {
            Remove-Item -LiteralPath $tempDir -Recurse -Force
        }
    }
}

function Apply-RelayConfig {
    if (-not (Test-Path -LiteralPath $ManageUsersScript)) {
        Write-Host "找不到白名單工具：$ManageUsersScript" -ForegroundColor Red
        return
    }

    if (Test-Path -LiteralPath (Join-Path $ConfigDir 'relay_users.json')) {
        & $ManageUsersScript -Mode Apply
    } else {
        Write-Host '尚未有 relay_users.json。請稍後用「管理IRL白名單.bat」新增台主。' -ForegroundColor Yellow
    }
}

function Ensure-FirewallRule {
    param(
        [string]$DisplayName,
        [string]$Protocol,
        [int]$Port
    )

    $existing = Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "防火牆規則已存在：$DisplayName" -ForegroundColor Green
        return
    }

    New-NetFirewallRule -DisplayName $DisplayName -Direction Inbound -Action Allow -Protocol $Protocol -LocalPort $Port | Out-Null
    Write-Host "已新增防火牆規則：$DisplayName（$Protocol $Port）" -ForegroundColor Green
}

function Configure-Firewall {
    if (-not (Confirm-Step '是否設定 Windows 防火牆？會新增 UDP 8890；若需要其他電腦上的 NOALBS 遠端監測，也會詢問 TCP 9997。')) {
        Write-Host '已跳過防火牆設定。' -ForegroundColor DarkGray
        return
    }

    if (-not (Test-IsAdministrator)) {
        Write-Host '目前不是系統管理員權限，無法自動新增防火牆規則。' -ForegroundColor Red
        Write-Host '請用「以系統管理員身分執行」重新開啟這個初始化腳本。' -ForegroundColor Yellow
        return
    }

    Ensure-FirewallRule -DisplayName 'IRL MediaMTX SRT UDP 8890' -Protocol 'UDP' -Port 8890

    if (Confirm-Step '如果 NOALBS 不在中繼伺服器同一台電腦執行，需要連 http://你的網域:9997。是否開啟 TCP 9997？') {
        Ensure-FirewallRule -DisplayName 'IRL MediaMTX API TCP 9997' -Protocol 'TCP' -Port 9997
    } else {
        Write-Host '已跳過 TCP 9997。其他電腦上的 NOALBS 遠端監測可能不能用。' -ForegroundColor Yellow
    }
}

function Show-Summary {
    $localIp = Get-PrimaryIPv4
    Write-Host ''
    Write-Host '=============================' -ForegroundColor Cyan
    Write-Host '      筆電 IRL 初始化摘要     ' -ForegroundColor Cyan
    Write-Host '=============================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host "目前電腦名稱：$env:COMPUTERNAME"
    if ($localIp) {
        Write-Host "筆電目前內網 IP：$localIp" -ForegroundColor Green
    } else {
        Write-Host '無法自動判斷筆電內網 IP，請到網路設定查看。' -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host '路由器仍需要人工確認：' -ForegroundColor Yellow
    Write-Host '1. H660WM：UDP 5002 -> Deco WAN IP:5002'
    if ($localIp) {
        Write-Host "2. Deco：UDP 5002 -> $localIp`:8890"
        Write-Host "3. 若其他電腦上的 NOALBS 要遠端監測：H660WM TCP 9997 -> Deco WAN IP:9997，Deco TCP 9997 -> $localIp`:9997"
    } else {
        Write-Host '2. Deco：UDP 5002 -> 筆電內網 IP:8890'
        Write-Host '3. 若其他電腦上的 NOALBS 要遠端監測：H660WM TCP 9997 -> Deco WAN IP:9997，Deco TCP 9997 -> 筆電內網 IP:9997'
    }
    Write-Host ''
    Write-Host '下一步建議：' -ForegroundColor Cyan
    Write-Host "1. 筆電：若 Dynu 還沒設定，雙擊：$DynuLauncher"
    Write-Host "2. 筆電：若還沒建立白名單，雙擊：$UsersLauncher"
    Write-Host "3. 筆電：要開中繼伺服器，雙擊：$StartLauncher"
    Write-Host "4. 桌電：OBS 媒體來源改用 srt://筆電內網IP:8890?streamid=read:<Twitch ID>:<read user>:<read key>"
    Write-Host "5. 桌電：NOALBS statsUrl 改用 http://筆電內網IP:9997/v3/paths/get/<Twitch ID>"

    if ($localIp) {
        Write-Host ''
        Write-Host '用目前偵測到的筆電 IP 來看，桌電端要改成：' -ForegroundColor Cyan
        Write-Host "OBS：srt://$localIp`:8890?streamid=read:<Twitch ID>:<read user>:<read key>"
        Write-Host "NOALBS statsUrl：http://$localIp`:9997/v3/paths/get/<Twitch ID>"
    }
}

Write-Host ''
Write-Host '=============================' -ForegroundColor Cyan
Write-Host '      初始化筆電 IRL 環境     ' -ForegroundColor Cyan
Write-Host '=============================' -ForegroundColor Cyan
Write-Host ''
Write-Host "目標筆電：$ExpectedComputerName" -ForegroundColor Cyan
Write-Host "目前電腦：$env:COMPUTERNAME" -ForegroundColor Cyan

if ($env:COMPUTERNAME -ne $ExpectedComputerName) {
    if (-not (Confirm-Step "目前不是 $ExpectedComputerName。確定仍要繼續嗎？")) {
        Write-Host '已取消。' -ForegroundColor DarkGray
        exit 0
    }
}

if (-not $ImportZip) {
    $typedZip = (Read-Host '如果有筆電搬移包 zip，貼上完整路徑；沒有就直接按 Enter').Trim('" ')
    if ($typedZip) { $ImportZip = $typedZip }
}

Import-PrivateConfig -ZipPath $ImportZip
Install-MediaMtx
Apply-RelayConfig
Configure-Firewall
Show-Summary

if (Confirm-Step '是否現在啟動 IRL 中繼伺服器？') {
    Start-Process -FilePath $StartLauncher
}

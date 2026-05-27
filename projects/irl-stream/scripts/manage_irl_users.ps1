param(
    [ValidateSet('Menu', 'Apply')]
    [string]$Mode = 'Menu'
)

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$RelayHost = Get-IrlRelayHost
$SrtPort = 5002

$ProjectRoot = Get-IrlProjectRoot
$ConfigDir = Get-IrlConfigDir
$UsersFile = Join-Path $ConfigDir 'relay_users.json'
$ExportDir = Join-Path $ConfigDir 'exports'
$MediaMtxDir = Join-Path $ProjectRoot 'tools\mediamtx'
$MediaMtxExe = Join-Path $MediaMtxDir 'mediamtx.exe'
$MediaMtxConfig = Join-Path $ConfigDir 'mediamtx.yml'

function Ensure-Directories {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    New-Item -ItemType Directory -Path $ExportDir -Force | Out-Null
}

function New-EmptyState {
    [pscustomobject]@{
        version = 1
        users = [pscustomobject]@{}
    }
}

function Load-State {
    Ensure-Directories
    if (-not (Test-Path $UsersFile)) {
        return New-EmptyState
    }

    $state = Get-Content -LiteralPath $UsersFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $state.users) {
        $state | Add-Member -NotePropertyName users -NotePropertyValue ([pscustomobject]@{}) -Force
    }
    return $state
}

function Save-State {
    param([pscustomobject]$State)
    Ensure-Directories
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $UsersFile -Encoding UTF8
}

function Get-UserProperties {
    param([pscustomobject]$State)
    if (-not $State.users) { return @() }
    return @($State.users.PSObject.Properties | Sort-Object Name)
}

function Get-UserEntry {
    param(
        [pscustomobject]$State,
        [string]$TwitchId
    )
    $prop = $State.users.PSObject.Properties[$TwitchId]
    if ($prop) { return $prop.Value }
    return $null
}

function Set-UserEntry {
    param(
        [pscustomobject]$State,
        [string]$TwitchId,
        [pscustomobject]$Entry
    )
    $State.users | Add-Member -NotePropertyName $TwitchId -NotePropertyValue $Entry -Force
}

function Read-TwitchId {
    param([string]$Prompt = 'Twitch ID')

    do {
        $id = (Read-Host $Prompt).Trim().ToLower()
        if ($id -notmatch '^[a-z0-9_]{3,25}$') {
            Write-Host '請輸入 3-25 個英文小寫、數字或底線。' -ForegroundColor Red
            $id = $null
        }
    } while (-not $id)

    return $id
}

function New-Secret {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-UserEntry {
    param([string]$TwitchId)
    $now = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    [pscustomobject]@{
        enabled = $true
        publishUser = "pub_$TwitchId"
        publishKey = New-Secret
        readUser = "read_$TwitchId"
        readKey = New-Secret
        createdAt = $now
        updatedAt = $now
    }
}

function Update-UserTimestamp {
    param([pscustomobject]$Entry)
    $Entry | Add-Member -NotePropertyName updatedAt -NotePropertyValue ((Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')) -Force
}

function Get-UserSettingsText {
    param(
        [string]$TwitchId,
        [pscustomobject]$Entry
    )

    @"
戶外直播連線資料
================

Twitch ID：
$TwitchId

手機推流
--------
URL：
srt://$RelayHost`:$SrtPort

Stream ID：
publish:${TwitchId}:$($Entry.publishUser):$($Entry.publishKey)

OBS 媒體來源
------------
輸入：
srt://$RelayHost`:$SrtPort`?streamid=read:${TwitchId}:$($Entry.readUser):$($Entry.readKey)

提醒
----
這份資料只給本人使用，不要公開貼在聊天室或 Discord。
如果不借用了，管理員可以停用這組資料。
"@
}

function Write-MediaMtxConfig {
    param([pscustomobject]$State)

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('api: yes')
    $lines.Add('apiAddress: :9997')
    $lines.Add('srtAddress: :5002')
    $lines.Add('')
    $lines.Add('authInternalUsers:')
    $lines.Add('  - user: any')
    $lines.Add('    pass:')
    $lines.Add('    ips: []')
    $lines.Add('    permissions:')
    $lines.Add('      - action: api')
    $lines.Add('')

    foreach ($prop in Get-UserProperties $State) {
        $id = $prop.Name
        $entry = $prop.Value
        if (-not $entry.enabled) { continue }

        $lines.Add("  - user: $($entry.publishUser)")
        $lines.Add("    pass: $($entry.publishKey)")
        $lines.Add('    ips: []')
        $lines.Add('    permissions:')
        $lines.Add('      - action: publish')
        $lines.Add("        path: $id")
        $lines.Add('')
        $lines.Add("  - user: $($entry.readUser)")
        $lines.Add("    pass: $($entry.readKey)")
        $lines.Add('    ips: []')
        $lines.Add('    permissions:')
        $lines.Add('      - action: read')
        $lines.Add("        path: $id")
        $lines.Add('')
    }

    $lines.Add('paths:')
    $lines.Add('  all_others:')
    $lines.Add('')

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($MediaMtxConfig, ($lines -join "`r`n"), $utf8NoBom)
}

function Restart-MediaMtx {
    if (-not (Test-Path $MediaMtxExe)) {
        Write-Host "找不到 MediaMTX：$MediaMtxExe" -ForegroundColor Red
        return
    }

    $running = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
    if ($running) {
        Stop-Process -Name 'mediamtx' -Force
        Start-Sleep -Seconds 1
    }

    Start-Process -FilePath $MediaMtxExe -ArgumentList "`"$MediaMtxConfig`"" -WorkingDirectory $MediaMtxDir -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host 'MediaMTX 已用最新白名單重新啟動。' -ForegroundColor Green
}

function Apply-RunningMediaMtx {
    if (Get-Process 'mediamtx' -ErrorAction SilentlyContinue) {
        Write-Host 'MediaMTX 目前正在執行，正在自動重啟套用白名單...' -ForegroundColor Yellow
        Restart-MediaMtx
    } else {
        Write-Host 'MediaMTX 目前沒有執行；下次啟動直播環境時會自動套用白名單。' -ForegroundColor Yellow
    }
}

function Export-UserSettings {
    param(
        [pscustomObject]$State,
        [string]$TwitchId
    )

    $entry = Get-UserEntry $State $TwitchId
    if (-not $entry) {
        Write-Host "找不到 $TwitchId。" -ForegroundColor Red
        return
    }
    if (-not $entry.enabled) {
        Write-Host "$TwitchId 目前是停用狀態，仍會匯出資料方便備查。" -ForegroundColor Yellow
    }

    Ensure-Directories
    $text = Get-UserSettingsText -TwitchId $TwitchId -Entry $entry
    $file = Join-Path $ExportDir "$TwitchId-settings.txt"
    Set-Content -LiteralPath $file -Value $text -Encoding UTF8
    try {
        Set-Clipboard -Value $text
        Write-Host '設定內容已複製到剪貼簿。' -ForegroundColor Green
    } catch {
        Write-Host '剪貼簿不可用，已只輸出成檔案。' -ForegroundColor Yellow
    }
    Write-Host "給台主的設定已輸出：$file" -ForegroundColor Cyan
    Write-Host ''
    Write-Host '提醒：請把這份文字檔或剪貼簿內容給台主，台主照裡面填手機和 OBS。' -ForegroundColor Yellow
}

function Add-User {
    $state = Load-State
    $id = Read-TwitchId '要新增的 Twitch ID'
    $existing = Get-UserEntry $state $id

    if ($existing) {
        $existing.enabled = $true
        Update-UserTimestamp $existing
        Write-Host "已重新啟用 $id，原本密鑰保留。" -ForegroundColor Green
    } else {
        Set-UserEntry $state $id (New-UserEntry $id)
        Write-Host "已新增 $id。" -ForegroundColor Green
    }

    Save-State $state
    Write-MediaMtxConfig $state
    Export-UserSettings -State $state -TwitchId $id
    Apply-RunningMediaMtx
}

function Disable-User {
    $state = Load-State
    $id = Read-TwitchId '要停用的 Twitch ID'
    $entry = Get-UserEntry $state $id
    if (-not $entry) {
        Write-Host "找不到 $id。" -ForegroundColor Red
        return
    }

    $entry.enabled = $false
    Update-UserTimestamp $entry
    Save-State $state
    Write-MediaMtxConfig $state
    Write-Host "已停用 $id。" -ForegroundColor Green
    Apply-RunningMediaMtx
}

function Rotate-UserKeys {
    $state = Load-State
    $id = Read-TwitchId '要重新產生密鑰的 Twitch ID'
    $entry = Get-UserEntry $state $id
    if (-not $entry) {
        Write-Host "找不到 $id。" -ForegroundColor Red
        return
    }

    $entry.publishKey = New-Secret
    $entry.readKey = New-Secret
    Update-UserTimestamp $entry
    Save-State $state
    Write-MediaMtxConfig $state
    Export-UserSettings -State $state -TwitchId $id
    Write-Host "已重新產生 $id 的推流與拉流密鑰。" -ForegroundColor Green
    Apply-RunningMediaMtx
}

function List-Users {
    $state = Load-State
    $users = Get-UserProperties $state
    if ($users.Count -eq 0) {
        Write-Host '目前沒有台主。' -ForegroundColor Yellow
        return
    }

    Write-Host ''
    Write-Host '目前白名單：' -ForegroundColor Cyan
    foreach ($prop in $users) {
        $status = if ($prop.Value.enabled) { '啟用' } else { '停用' }
        Write-Host ("  {0,-25} {1}  更新：{2}" -f $prop.Name, $status, $prop.Value.updatedAt)
    }
}

function Export-UserSettingsInteractive {
    $state = Load-State
    $id = Read-TwitchId '要匯出的 Twitch ID'
    Export-UserSettings -State $state -TwitchId $id
}

function Remove-User {
    $state = Load-State
    $id = Read-TwitchId '要刪除的 Twitch ID'
    $entry = Get-UserEntry $state $id
    if (-not $entry) {
        Write-Host "找不到 $id。" -ForegroundColor Red
        return
    }

    Write-Host "即將完全刪除 $id（包含密鑰資料，無法復原）" -ForegroundColor Yellow
    $confirm = (Read-Host '確認刪除？（輸入 y 確認）').Trim().ToLower()
    if ($confirm -ne 'y') {
        Write-Host '已取消。' -ForegroundColor DarkGray
        return
    }

    $state.users.PSObject.Properties.Remove($id)
    Save-State $state
    Write-MediaMtxConfig $state
    Write-Host "已刪除 $id。" -ForegroundColor Green
    Apply-RunningMediaMtx
}

function Apply-Config {
    $state = Load-State
    Write-MediaMtxConfig $state
    Write-Host "已套用白名單到 MediaMTX 設定：$MediaMtxConfig" -ForegroundColor Green
}

function Show-Menu {
    Clear-Host
    Write-Host '=============================' -ForegroundColor Cyan
    Write-Host '      IRL 白名單管理工具      ' -ForegroundColor Cyan
    Write-Host '=============================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '1. 新增台主'
    Write-Host '2. 停用台主'
    Write-Host '3. 重新產生密鑰'
    Write-Host '4. 查看目前名單'
    Write-Host '5. 匯出給台主的設定'
    Write-Host '6. 套用白名單到 MediaMTX 設定'
    Write-Host '7. 套用並重啟 MediaMTX'
    Write-Host '8. 刪除台主（完全移除）'
    Write-Host '0. 離開'
    Write-Host ''
}

if ($Mode -eq 'Apply') {
    Apply-Config
    exit 0
}

do {
    Show-Menu
    $choice = (Read-Host '請輸入功能編號').Trim()
    Write-Host ''

    switch ($choice) {
        '1' { Add-User }
        '2' { Disable-User }
        '3' { Rotate-UserKeys }
        '4' { List-Users }
        '5' { Export-UserSettingsInteractive }
        '6' { Apply-Config }
        '7' { Apply-Config; Restart-MediaMtx }
        '8' { Remove-User }
        '0' { break }
        default { Write-Host '沒有這個功能。' -ForegroundColor Red }
    }

    if ($choice -ne '0') {
        Write-Host ''
        Read-Host '按 Enter 回到選單'
    }
} while ($choice -ne '0')

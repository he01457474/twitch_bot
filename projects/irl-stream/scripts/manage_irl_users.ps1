param(
    [ValidateSet('Menu', 'Apply')]
    [string]$Mode = 'Menu'
)

$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$RelayHost = Get-IrlRelayHost
$PublicSrtPort = 5002
$LocalSrtPort = 8890

$ProjectRoot = Get-IrlProjectRoot
$ConfigDir = Get-IrlConfigDir
$UsersFile = Join-Path $ConfigDir 'relay_users.json'
$ExportDir = Join-Path $ConfigDir 'exports'
$MediaMtxDir = Join-Path $ProjectRoot 'tools\mediamtx'
$MediaMtxExe = Join-Path $MediaMtxDir 'mediamtx.exe'
$MediaMtxConfig = Join-Path $ConfigDir 'mediamtx.yml'
$MediaMtxWatchdogPidFile = "$env:TEMP\mediamtx_watchdog.pid"

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

function Select-UserFromList {
    param(
        [pscustomobject]$State,
        [string]$Prompt = '請選擇台主編號'
    )

    $users = Get-UserProperties $State
    if ($users.Count -eq 0) {
        Write-Host '目前沒有台主。' -ForegroundColor Yellow
        return $null
    }

    Write-Host ''
    $i = 1
    foreach ($prop in $users) {
        $status = if ($prop.Value.enabled) { '啟用' } else { '停用' }
        Write-Host ("  {0}.  {1,-25}  {2}" -f $i, $prop.Name, $status)
        $i++
    }
    Write-Host ''

    do {
        $input = (Read-Host $Prompt).Trim()
        $n = 0
        if (-not [int]::TryParse($input, [ref]$n) -or $n -lt 1 -or $n -gt $users.Count) {
            Write-Host "請輸入 1 到 $($users.Count) 的數字。" -ForegroundColor Red
            $n = 0
        }
    } while ($n -eq 0)

    return $users[$n - 1].Name
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

一、手機推流 App 要填這兩欄
----------------------------
把下面兩行分別貼到 IRL Pro / Moblin 的 SRT 設定。

URL / Host：
srt://$RelayHost`:$PublicSrtPort

如果 App 沒有 URL 欄位，請拆開填：
Host：$RelayHost
Port：$PublicSrtPort

Stream ID / streamid：
publish:${TwitchId}:$($Entry.publishUser):$($Entry.publishKey)

二、OBS 媒體來源要填這一整串
----------------------------
OBS → IRL 場景 → 媒體來源 → 取消「本機檔案」→「輸入」貼下面整串：

srt://$RelayHost`:$PublicSrtPort`?streamid=read:${TwitchId}:$($Entry.readUser):$($Entry.readKey)

OBS 其他建議：
輸入格式：mpegts
重新連線延遲：3 秒
手機如果送 H265 / HEVC 但 OBS 黑畫面，請把手機編碼改成 H264 / AVC。

三、每次直播順序
----------------
開始：
1. 管理員確認中繼伺服器已啟動
2. 你先開 OBS
3. 雙擊「啟動_NOALBS.bat」
4. 手機開始推流
5. Twitch 聊天室打 !start

結束：
1. Twitch 聊天室打 !stop
2. 手機停止推流
3. 雙擊「關閉_NOALBS.bat」
4. 關閉 OBS

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
    $lines.Add("srtAddress: :$LocalSrtPort")
    $lines.Add('readBufferCount: 256')
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

function Stop-MediaMtxWatchdog {
    $savedPid = $null
    if (Test-Path $MediaMtxWatchdogPidFile) {
        $rawPid = Get-Content $MediaMtxWatchdogPidFile -ErrorAction SilentlyContinue
        if ($rawPid -and $rawPid -match '^\d+$') {
            $savedPid = [int]$rawPid
            Stop-Process -Id $savedPid -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $MediaMtxWatchdogPidFile -ErrorAction SilentlyContinue
        Write-Host 'MediaMTX 監控已先關閉，避免重啟時又自動拉起舊設定。' -ForegroundColor DarkGray
    }
    return $savedPid
}

function Stop-MediaMtxForRestart {
    $watchdogPid = Stop-MediaMtxWatchdog
    $running = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
    if (-not $running) { return $true }

    try {
        Stop-Process -Name 'mediamtx' -Force -ErrorAction Stop
        Start-Sleep -Seconds 1
    } catch {
        Write-Host '無法用目前權限停止 MediaMTX，準備要求管理員權限終止。' -ForegroundColor Yellow
        $wdCmd = ''
        if ($watchdogPid) {
            $wdCmd = "Stop-Process -Id $watchdogPid -Force -ErrorAction SilentlyContinue; "
        }
        $killCmd = "${wdCmd}Stop-Process -Name mediamtx -Force -ErrorAction SilentlyContinue"
        $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($killCmd))

        try {
            Start-Process powershell -Verb RunAs -WindowStyle Hidden -Wait `
                -ArgumentList "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $enc" `
                -ErrorAction Stop
            Start-Sleep -Milliseconds 800
        } catch {
            Write-Host '提權取消，MediaMTX 沒有停止；白名單已寫入，但目前執行中的伺服器還沒套用。' -ForegroundColor Red
            Write-Host '請先用「關閉直播環境.bat」或工作管理員結束 mediamtx.exe，再重新啟動直播環境。' -ForegroundColor Yellow
            return $false
        }
    }

    if (Get-Process 'mediamtx' -ErrorAction SilentlyContinue) {
        Write-Host 'MediaMTX 仍在執行；白名單已寫入，但目前執行中的伺服器還沒套用。' -ForegroundColor Red
        Write-Host '請先用「關閉直播環境.bat」或工作管理員結束 mediamtx.exe，再重新啟動直播環境。' -ForegroundColor Yellow
        return $false
    }

    return $true
}

function Restart-MediaMtx {
    if (-not (Test-Path $MediaMtxExe)) {
        Write-Host "找不到 MediaMTX：$MediaMtxExe" -ForegroundColor Red
        return
    }

    if (-not (Stop-MediaMtxForRestart)) {
        return
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

function Export-UserBundle {
    param(
        [pscustomobject]$State,
        [string]$TwitchId
    )
    $entry = Get-UserEntry $State $TwitchId
    if (-not $entry) { Write-Host "找不到 $TwitchId。" -ForegroundColor Red; return }
    if (-not $entry.enabled) {
        Write-Host "$TwitchId 目前是停用狀態，仍會匯出資料方便備查。" -ForegroundColor Yellow
    }

    Ensure-Directories
    $text = Get-UserSettingsText -TwitchId $TwitchId -Entry $entry
    $settingsFile = Join-Path $ExportDir "$TwitchId-settings.txt"
    Set-Content -LiteralPath $settingsFile -Value $text -Encoding UTF8

    $installBat = Join-Path $ProjectRoot 'launchers\install_noalbs.bat'
    $zipFile    = Join-Path $ExportDir "$TwitchId-irl-bundle.zip"
    $tempDir    = Join-Path $env:TEMP "irl_bundle_$TwitchId"

    if (Test-Path $zipFile) { Remove-Item $zipFile -Force }
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    Copy-Item -LiteralPath $settingsFile -Destination (Join-Path $tempDir "$TwitchId-settings.txt")
    if (Test-Path $installBat) {
        Copy-Item -LiteralPath $installBat -Destination (Join-Path $tempDir 'install_noalbs.bat')
    } else {
        Write-Host '  [警告] 找不到 install_noalbs.bat，zip 內只含設定文字。' -ForegroundColor Yellow
    }

    Compress-Archive -Path "$tempDir\*" -DestinationPath $zipFile -Force
    Remove-Item $tempDir -Recurse -Force

    try { Set-Clipboard -Value $text; Write-Host '設定內容已複製到剪貼簿。' -ForegroundColor Green }
    catch { Write-Host '剪貼簿不可用，已只輸出成檔案。' -ForegroundColor Yellow }
    Write-Host "台主包已產生：$zipFile" -ForegroundColor Cyan
    Write-Host '請把這個 zip 傳給台主，解壓縮後跑 install_noalbs.bat 即可完成設定。' -ForegroundColor Yellow
    Start-Process explorer.exe $ExportDir
}

function Export-AllUserSettingsFiles {
    param([pscustomObject]$State)

    Ensure-Directories
    foreach ($prop in Get-UserProperties $State) {
        $id = $prop.Name
        $entry = $prop.Value
        $text = Get-UserSettingsText -TwitchId $id -Entry $entry
        $file = Join-Path $ExportDir "$id-settings.txt"
        Set-Content -LiteralPath $file -Value $text -Encoding UTF8
    }
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
    Export-UserBundle -State $state -TwitchId $id
    Apply-RunningMediaMtx
}

function Disable-User {
    $state = Load-State
    $id = Select-UserFromList $state '要停用的台主編號'
    if (-not $id) { return }
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
    $id = Select-UserFromList $state '要重新產生密鑰的台主編號'
    if (-not $id) { return }
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
    Write-Host "已重新產生 $id 的推流與拉流密鑰。" -ForegroundColor Green
    Export-UserBundle -State $state -TwitchId $id
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
        $ts = try { [datetime]::Parse($prop.Value.updatedAt).ToString('yyyy-MM-dd HH:mm') } catch { $prop.Value.updatedAt }
        Write-Host ("  {0,-25}  {1,-4}  更新：{2}" -f $prop.Name, $status, $ts)
    }
}

function Export-UserBundleInteractive {
    $state = Load-State
    $id = Select-UserFromList $state '要匯出台主包的台主編號'
    if (-not $id) { return }
    Export-UserBundle -State $state -TwitchId $id
}

function Remove-User {
    $state = Load-State
    $id = Select-UserFromList $state '要刪除的台主編號'
    if (-not $id) { return }
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
    Export-AllUserSettingsFiles $state
    Write-Host "已套用白名單到 MediaMTX 設定：$MediaMtxConfig" -ForegroundColor Green
    Write-Host "已同步更新台主設定文字檔：$ExportDir" -ForegroundColor Green
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
    Write-Host '5. 匯出台主包（zip）'
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
        '5' { Export-UserBundleInteractive }
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

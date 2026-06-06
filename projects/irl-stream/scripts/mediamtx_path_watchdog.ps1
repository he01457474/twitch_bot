param(
    [string]$PidFile = "$env:TEMP\mediamtx_path_watchdog.pid"
)

$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$NotifyScript = Join-Path $PSScriptRoot 'send_irl_notification.ps1'
$UsersFile = Join-Path (Get-IrlConfigDir) 'relay_users.json'
$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII

function Send-AdminNotification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Level = 'Info',
        [string]$Key = '',
        [int]$CooldownMinutes = 1
    )
    if (Test-Path -LiteralPath $NotifyScript) {
        & $NotifyScript -Title $Title -Message $Message -Level $Level -Key $Key -CooldownMinutes $CooldownMinutes
    }
}

function Get-EnabledUserIds {
    if (-not (Test-Path -LiteralPath $UsersFile)) { return @() }
    try {
        $state = Get-Content -LiteralPath $UsersFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if (-not $state.users) { return @() }
        $ids = @()
        foreach ($prop in $state.users.PSObject.Properties) {
            if ($prop.Value.enabled) { $ids += [string]$prop.Name }
        }
        return $ids
    } catch {
        return @()
    }
}

function Get-ActivePathIds {
    param([string[]]$EnabledIds)
    $active = @{}
    if ($EnabledIds.Count -eq 0) { return $active }

    try {
        $response = Invoke-RestMethod -Uri 'http://localhost:9997/v3/paths/list' -UseBasicParsing -TimeoutSec 5
        foreach ($item in @($response.items)) {
            $name = [string]$item.name
            if (-not $name -or $EnabledIds -notcontains $name) { continue }

            $ready = $false
            if ($item.PSObject.Properties['sourceReady']) {
                $ready = [bool]$item.sourceReady
            } elseif ($item.PSObject.Properties['source'] -and $item.source) {
                $ready = $true
            }

            if ($ready) { $active[$name] = $true }
        }
    } catch {
    }

    return $active
}

$previous = @{}

while ($true) {
    Start-Sleep -Seconds 20
    $enabled = @(Get-EnabledUserIds)
    $current = Get-ActivePathIds -EnabledIds $enabled

    foreach ($id in $current.Keys) {
        if (-not $previous.ContainsKey($id)) {
            Send-AdminNotification `
                -Title '台主開始推流' `
                -Message "台主 $id 已進入 MediaMTX。" `
                -Level Success `
                -Key "path-start-$id" `
                -CooldownMinutes 1
        }
    }

    foreach ($id in $previous.Keys) {
        if (-not $current.ContainsKey($id)) {
            Send-AdminNotification `
                -Title '台主停止推流' `
                -Message "台主 $id 已離開 MediaMTX。" `
                -Level Warning `
                -Key "path-stop-$id" `
                -CooldownMinutes 1
        }
    }

    $previous = $current
}

param(
    [Parameter(Mandatory = $true)]
    [string]$Title,
    [string]$Message = '',
    [ValidateSet('Info', 'Success', 'Warning', 'Error')]
    [string]$Level = 'Info',
    [string]$Key = '',
    [int]$CooldownMinutes = -1
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

function Get-NotificationConfigPath {
    return Join-Path (Get-IrlConfigDir) 'notification.json'
}

function Get-NotificationStatePath {
    return Join-Path (Get-IrlConfigDir) 'notification_state.json'
}

function Load-JsonObject {
    param(
        [string]$Path,
        [scriptblock]$DefaultFactory
    )
    if (Test-Path -LiteralPath $Path) {
        try {
            return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
        }
    }
    return & $DefaultFactory
}

function Save-JsonObject {
    param(
        [string]$Path,
        [object]$Value
    )
    New-Item -ItemType Directory -Path (Split-Path -Parent $Path) -Force | Out-Null
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

try {
    $configPath = Get-NotificationConfigPath
    if (-not (Test-Path -LiteralPath $configPath)) { exit 0 }

    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.enabled -eq $false) { exit 0 }
    if ([string]$config.provider -and ([string]$config.provider) -ne 'Discord') { exit 0 }

    $webhookUrl = [string]$config.discordWebhookUrl
    if (-not $webhookUrl) { exit 0 }

    if ($CooldownMinutes -lt 0) {
        if ($null -ne $config.cooldownMinutes) {
            $CooldownMinutes = [int]$config.cooldownMinutes
        } else {
            $CooldownMinutes = 5
        }
    }

    if (-not $Key) {
        $Key = ($Title -replace '[^\w.-]+', '_').Trim('_')
        if (-not $Key) { $Key = 'default' }
    }

    if ($CooldownMinutes -gt 0) {
        $statePath = Get-NotificationStatePath
        $state = Load-JsonObject -Path $statePath -DefaultFactory { [pscustomobject]@{ sent = [pscustomobject]@{} } }
        if (-not $state.sent) {
            $state | Add-Member -NotePropertyName sent -NotePropertyValue ([pscustomobject]@{}) -Force
        }

        $lastValue = $state.sent.PSObject.Properties[$Key].Value
        if ($lastValue) {
            try {
                $last = [datetime]::Parse([string]$lastValue)
                if (((Get-Date) - $last).TotalMinutes -lt $CooldownMinutes) {
                    exit 0
                }
            } catch {
            }
        }

        $state.sent | Add-Member -NotePropertyName $Key -NotePropertyValue ((Get-Date).ToString('o')) -Force
        Save-JsonObject -Path $statePath -Value $state
    }

    $color = switch ($Level) {
        'Success' { 5763719 }
        'Warning' { 16763904 }
        'Error' { 15548997 }
        default { 3447003 }
    }

    $description = $Message
    if (-not $description) { $description = $Title }

    $payload = [pscustomobject]@{
        username = 'FlyCat IRL'
        embeds = @(
            [pscustomobject]@{
                title = $Title
                description = $description
                color = $color
                fields = @(
                    [pscustomobject]@{ name = '電腦'; value = $env:COMPUTERNAME; inline = $true },
                    [pscustomobject]@{ name = '時間'; value = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); inline = $true }
                )
            }
        )
    }

    $body = $payload | ConvertTo-Json -Depth 8
    Invoke-RestMethod -Uri $webhookUrl -Method Post -ContentType 'application/json; charset=utf-8' -Body $body | Out-Null
} catch {
    # Notification must never break the relay scripts.
    exit 0
}

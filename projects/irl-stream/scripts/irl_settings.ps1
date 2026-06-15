function Get-IrlProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-IrlConfigDir {
    return Join-Path (Get-IrlProjectRoot) 'config'
}

function Get-IrlRelaySettingsPath {
    return Join-Path (Get-IrlConfigDir) 'relay_settings.json'
}

function Get-IrlDefaultRelayHost {
    return 'flycatirl.ddnsgeek.com'
}

function Get-IrlRelayHost {
    $settingsPath = Get-IrlRelaySettingsPath
    if (Test-Path $settingsPath) {
        try {
            $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($settings.relayHost) {
                return [string]$settings.relayHost
            }
        } catch {
            Write-Host "讀取 relay_settings.json 失敗，改用預設網址：$($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    return Get-IrlDefaultRelayHost
}

function Get-IrlStopFlagPath {
    return "$env:TEMP\irl_relay_stopping.flag"
}

function Set-IrlRelayHost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelayHost,
        [string]$Provider = 'Dynu'
    )

    $configDir = Get-IrlConfigDir
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null

    $settings = [pscustomobject]@{
        relayHost = $RelayHost.Trim().ToLower()
        ddnsProvider = $Provider
        updatedAt = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    }

    $json = $settings | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText((Get-IrlRelaySettingsPath), $json, [System.Text.UTF8Encoding]::new($false))
}

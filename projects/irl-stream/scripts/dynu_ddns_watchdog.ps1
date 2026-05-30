param(
    [string]$PidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

$PID | Set-Content -LiteralPath $PidFile -Encoding ASCII
$updateScript = Join-Path $PSScriptRoot 'update_dynu_ddns.ps1'

while ($true) {
    try {
        & $updateScript | Out-Null
    } catch {
        # Keep retrying while the IRL environment is open.
    }
    Start-Sleep -Seconds 300
}

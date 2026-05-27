chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

. (Join-Path $PSScriptRoot 'irl_settings.ps1')

$ConfigDir = Get-IrlConfigDir
$DynuConfig = Join-Path $ConfigDir 'dynu_ddns.json'

if (-not (Test-Path $DynuConfig)) {
    Write-Host "尚未設定 Dynu DDNS，請先執行「設定DynuDDNS.bat」。" -ForegroundColor Yellow
    return
}

$config = Get-Content -LiteralPath $DynuConfig -Raw -Encoding UTF8 | ConvertFrom-Json
$hostname = [string]$config.hostname
$username = [string]$config.username

if (-not $hostname -or -not $username -or -not $config.password) {
    throw 'Dynu 設定不完整，請重新執行「設定DynuDDNS.bat」。'
}

if ($config.passwordEncoding -eq 'base64-utf8') {
    $password = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$config.password))
} else {
    throw 'Dynu 密碼格式已過期，請重新執行「設定DynuDDNS.bat」。'
}

$query = @{
    hostname = $hostname
    username = $username
    password = $password
    myipv6 = 'no'
}

$parts = foreach ($item in $query.GetEnumerator()) {
    '{0}={1}' -f [Uri]::EscapeDataString($item.Key), [Uri]::EscapeDataString([string]$item.Value)
}
$uri = 'https://api.dynu.com/nic/update?' + ($parts -join '&')

try {
    $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 20
    $body = ($response.Content | Out-String).Trim()
} catch {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $node) { throw }

    $nodeCode = @'
const url = process.argv[1];
fetch(url)
  .then(async (response) => {
    const text = await response.text();
    if (!response.ok) {
      console.error(text || response.statusText);
      process.exit(1);
    }
    process.stdout.write(text);
  })
  .catch((error) => {
    console.error(error && error.message ? error.message : String(error));
    process.exit(1);
  });
'@
    $body = (& $node.Source -e $nodeCode $uri 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Dynu HTTPS 連線失敗：$body"
    }
}

if ($body -match '^(good|nochg)\b') {
    Write-Host "Dynu DDNS 已更新：$hostname（$body）" -ForegroundColor Green
    return
}

throw "Dynu 更新失敗：$body"

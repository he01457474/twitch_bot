$port       = 8080
$projectTools = Resolve-Path "$PSScriptRoot\..\tools" -ErrorAction SilentlyContinue
if ($projectTools) {
    $root = $projectTools.Path
} else {
    $root = $PSScriptRoot
}
$configPath = Join-Path $root "brb-config.json"
$gqlUrl     = "https://gql.twitch.tv/gql"
$clientId   = "kimne78kx3ncx6brgo4mv6wki5h1ko"
$clipAccessQuery = 'query VideoAccessToken_Clip($slug: ID!) { clip(slug: $slug) { playbackAccessToken(params: {platform: "web", playerBackend: "mediaplayer", playerType: "site"}) { signature value } videoQualities { quality sourceURL } } }'
$nodeFetchScriptContent = @'
const https = require("https");

const url = process.argv[2];
const clientId = process.argv[3];
const body = Buffer.from(process.argv[4], "base64");

const req = https.request(url, {
  method: "POST",
  headers: {
    "Client-Id": clientId,
    "Content-Type": "application/json",
    "Content-Length": body.length
  }
}, (res) => {
  const chunks = [];
  res.on("data", (chunk) => chunks.push(chunk));
  res.on("end", () => {
    const text = Buffer.concat(chunks).toString("utf8");
    if (res.statusCode < 200 || res.statusCode >= 300) {
      console.error(text || res.statusMessage || ("HTTP " + res.statusCode));
      process.exit(1);
    }
    process.stdout.write(text);
  });
});

req.on("error", (error) => {
  console.error(error && error.message ? error.message : String(error));
  process.exit(1);
});

req.write(body);
req.end();
'@

function Invoke-TwitchGqlBody($body) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    try {
        $r = Invoke-WebRequest -Uri $gqlUrl -Method POST -UseBasicParsing -ErrorAction Stop `
            -Headers @{ "Client-Id" = $clientId; "Content-Type" = "application/json" } `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
        return $r.Content
    } catch {
        $node = Get-Command node.exe -ErrorAction SilentlyContinue
        if (-not $node) { throw }

        $body64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($body))
        $output = ($nodeFetchScriptContent | & $node.Source - $gqlUrl $clientId $body64 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Twitch GQL 連線失敗：$output"
        }
        return $output
    }
}

function Read-Config {
    if (Test-Path $configPath) {
        return Get-Content $configPath -Raw | ConvertFrom-Json
    }
    return [PSCustomObject]@{ channel = "sweet_0530"; volume = 0.2 }
}

function Invoke-GQL($query) {
    $body = [System.Text.Encoding]::UTF8.GetBytes(
        (ConvertTo-Json @{ query = $query } -Compress)
    )
    return ((Invoke-TwitchGqlBody ([System.Text.Encoding]::UTF8.GetString($body))) | ConvertFrom-Json)
}

function Get-ClipSlugs($channel) {
    $slugs  = @()
    $cursor = $null
    do {
        $afterClause = if ($cursor) { ",after:`"$cursor`"" } else { "" }
        $d = Invoke-GQL "{ user(login:`"$channel`"){clips(first:50$afterClause){pageInfo{hasNextPage endCursor}edges{node{slug}}}} }"
        $clips = $d.data.user.clips
        $slugs += @($clips.edges | ForEach-Object { $_.node.slug })
        $cursor = if ($clips.pageInfo.hasNextPage -and $slugs.Count -lt 50) { $clips.pageInfo.endCursor } else { $null }
    } while ($cursor)
    return $slugs
}

function Get-SignedUrl($slug) {
    $payload = @(
        @{
            operationName = "VideoAccessToken_Clip"
            variables     = @{ slug = $slug }
            query         = $clipAccessQuery
        }
    )
    $body = ConvertTo-Json -InputObject $payload -Compress -Depth 8
    $json    = (Invoke-TwitchGqlBody $body) | ConvertFrom-Json
    $d       = $json[0].data.clip
    if (-not $d) { throw "找不到 Twitch 剪輯資料：$slug" }
    $sig     = $d.playbackAccessToken.signature
    $token   = $d.playbackAccessToken.value
    $qs      = $d.videoQualities
    $srcUrl  = ($qs | Where-Object { $_.quality -eq "1080" } | Select-Object -First 1).sourceURL
    if (-not $srcUrl) { $srcUrl = ($qs | Select-Object -First 1).sourceURL }
    if (-not $srcUrl -or -not $sig -or -not $token) { throw "Twitch 剪輯影片網址不完整：$slug" }
    $tokenEnc = [System.Uri]::EscapeDataString($token)
    return "$srcUrl`?sig=$sig&token=$tokenEnc"
}

# 共用快取（執行緒安全 Hashtable）
$cache = [hashtable]::Synchronized(@{
    urls      = [hashtable]::Synchronized(@{})
    allDone   = $false
    lastFetch = [datetime]::MinValue
    channel   = ""
})

function Start-BgFetch($slugs) {
    $cache.allDone = $false
    $ps = [powershell]::Create()
    $ps.AddScript({
        param($slugs, $cache, $gqlUrl, $clientId, $clipAccessQuery, $nodeFetchScriptContent)
        function Invoke-TwitchGqlBody($body) {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            try {
                $r = Invoke-WebRequest -Uri $gqlUrl -Method POST -UseBasicParsing -ErrorAction Stop `
                    -Headers @{ "Client-Id" = $clientId; "Content-Type" = "application/json" } `
                    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
                return $r.Content
            } catch {
                $node = Get-Command node.exe -ErrorAction SilentlyContinue
                if (-not $node) { throw }

                $body64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($body))
                $output = ($nodeFetchScriptContent | & $node.Source - $gqlUrl $clientId $body64 2>&1 | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) {
                    throw "Twitch GQL 連線失敗：$output"
                }
                return $output
            }
        }
        function Get-SignedUrl($slug) {
            $payload = @(
                @{
                    operationName = "VideoAccessToken_Clip"
                    variables     = @{ slug = $slug }
                    query         = $clipAccessQuery
                }
            )
            $body = ConvertTo-Json -InputObject $payload -Compress -Depth 8
            $json   = (Invoke-TwitchGqlBody $body) | ConvertFrom-Json
            $d      = $json[0].data.clip
            if (-not $d) { throw "找不到 Twitch 剪輯資料：$slug" }
            $sig    = $d.playbackAccessToken.signature
            $token  = $d.playbackAccessToken.value
            $qs     = $d.videoQualities
            $srcUrl = ($qs | Where-Object { $_.quality -eq "1080" } | Select-Object -First 1).sourceURL
            if (-not $srcUrl) { $srcUrl = ($qs | Select-Object -First 1).sourceURL }
            if (-not $srcUrl -or -not $sig -or -not $token) { throw "Twitch 剪輯影片網址不完整：$slug" }
            $tokenEnc = [System.Uri]::EscapeDataString($token)
            return ($srcUrl + "?sig=" + $sig + "&token=" + $tokenEnc)
        }
        foreach ($slug in $slugs) {
            if (-not $cache.urls.ContainsKey($slug)) {
                try {
                    $url = Get-SignedUrl $slug
                    if ($url) { $cache.urls[$slug] = $url }
                } catch {}
                Start-Sleep -Milliseconds 150
            }
        }
        $cache.allDone   = $true
        $cache.lastFetch = [datetime]::UtcNow
    }).AddArgument($slugs).AddArgument($cache).AddArgument($gqlUrl).AddArgument($clientId).AddArgument($clipAccessQuery).AddArgument($nodeFetchScriptContent) | Out-Null
    $rs = [System.Management.Automation.Runspaces.RunspaceFactory]::CreateRunspace()
    $rs.Open()
    $ps.Runspace = $rs
    $ps.BeginInvoke() | Out-Null
}

function Refresh-Clips($channel) {
    Write-Host "[BRB] 抓取剪輯清單..."
    $slugs = Get-ClipSlugs $channel
    if ($slugs.Count -eq 0) { Write-Host "[BRB] 沒有找到剪輯"; return }

    # 清掉舊快取
    $cache.urls.Clear()
    $cache.channel = $channel

    # 先同步抓前 5 支，馬上可以播
    $first5 = $slugs | Select-Object -First 5
    foreach ($slug in $first5) {
        try {
            $url = Get-SignedUrl $slug
            if ($url) { $cache.urls[$slug] = $url }
        } catch {}
    }
    Write-Host "[BRB] 前 5 支已就緒，開始背景載入其餘 $($slugs.Count - 5) 支..."

    # 剩下的背景抓
    $rest = $slugs | Select-Object -Skip 5
    if ($rest.Count -gt 0) { Start-BgFetch $rest }
    else { $cache.allDone = $true; $cache.lastFetch = [datetime]::UtcNow }
}

# ── 啟動 ──────────────────────────────────────────────
$cfg     = Read-Config
$channel = $cfg.channel
Refresh-Clips $channel

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()
Write-Host "[BRB] 伺服器啟動：http://localhost:$port/brb-clips.html"
Write-Host "[BRB] 關閉此視窗即停止"

$notifiedDone = $false

while ($listener.IsListening) {
    $ctx  = $listener.GetContext()
    $path = $ctx.Request.Url.LocalPath
    $res  = $ctx.Response
    $res.Headers.Add("Access-Control-Allow-Origin", "*")

    # 背景載入完成通知（只印一次）
    if (-not $notifiedDone -and $cache.allDone) {
        $notifiedDone = $true
        Write-Host ("[BRB] 全部剪輯載入完成！共 " + $cache.urls.Count + " 支") -ForegroundColor Green
    }

    if ($path -eq "/api/config") {
        $payload = Get-Content $configPath -Raw
        $bytes   = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $res.ContentType     = "application/json"
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)

    } elseif ($path -eq "/api/clips") {
        # 切頻道或超時重抓
        $latestCfg = Read-Config
        if ($latestCfg.channel -ne $cache.channel) {
            $channel = $latestCfg.channel
            Refresh-Clips $channel
        } elseif ($cache.allDone -and ([datetime]::UtcNow - $cache.lastFetch).TotalMinutes -gt 30) {
            Refresh-Clips $cache.channel
        }
        # 回傳目前已有的 URL（包含背景還在跑的進度）
        $payload = $cache.urls | ConvertTo-Json -Compress
        $bytes   = [System.Text.Encoding]::UTF8.GetBytes($payload)
        $res.ContentType     = "application/json"
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)

    } else {
        $reqPath  = $path.TrimStart("/")
        if ($reqPath -eq "") { $reqPath = "brb-clips.html" }
        $filePath = Join-Path $root $reqPath

        if (Test-Path $filePath -PathType Leaf) {
            $ext  = [System.IO.Path]::GetExtension($filePath).ToLower()
            $mime = switch ($ext) {
                ".html" { "text/html; charset=utf-8" }
                ".js"   { "application/javascript" }
                ".css"  { "text/css" }
                default { "application/octet-stream" }
            }
            $bytes = [System.IO.File]::ReadAllBytes($filePath)
            $res.ContentType     = $mime
            $res.ContentLength64 = $bytes.Length
            $res.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
            $res.StatusCode = 404
        }
    }
    $res.OutputStream.Close()
}

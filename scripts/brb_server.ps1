chcp 65001 | Out-Null
$port       = 8080
$root       = (Resolve-Path "$PSScriptRoot\..\tools").Path
$configPath = Join-Path $root "brb-config.json"
$gqlUrl     = "https://gql.twitch.tv/gql"
$clientId   = "kimne78kx3ncx6brgo4mv6wki5h1ko"

function Read-Config {
    if (Test-Path $configPath) {
        return Get-Content $configPath -Raw | ConvertFrom-Json
    }
    return [PSCustomObject]@{ channel = "sweet_0530"; volume = 0.8 }
}

function Invoke-GQL($query) {
    $body = [System.Text.Encoding]::UTF8.GetBytes(
        (ConvertTo-Json @{ query = $query } -Compress)
    )
    $r = Invoke-WebRequest -Uri $gqlUrl -Method POST -UseBasicParsing `
        -Headers @{ "Client-Id" = $clientId; "Content-Type" = "application/json" } `
        -Body $body
    return ($r.Content | ConvertFrom-Json)
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
    $body = ConvertTo-Json @(
        @{
            operationName = "VideoAccessToken_Clip"
            variables     = @{ slug = $slug }
            extensions    = @{ persistedQuery = @{ version = 1; sha256Hash = "36b89d2507fce29e5ca551df756d27c1cfe079e2609642b4390aa4c35796eb11" } }
        }
    ) -Compress -Depth 5
    $r = Invoke-WebRequest -Uri $gqlUrl -Method POST -UseBasicParsing `
        -Headers @{ "Client-Id" = $clientId; "Content-Type" = "application/json" } `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
    $d       = ($r.Content | ConvertFrom-Json)[0].data.clip
    $sig     = $d.playbackAccessToken.signature
    $token   = $d.playbackAccessToken.value
    $qs      = $d.videoQualities
    $srcUrl  = ($qs | Where-Object { $_.quality -eq "1080" } | Select-Object -First 1).sourceURL
    if (-not $srcUrl) { $srcUrl = ($qs | Select-Object -First 1).sourceURL }
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
        param($slugs, $cache, $gqlUrl, $clientId)
        function Get-SignedUrl($slug) {
            $body = '[{"operationName":"VideoAccessToken_Clip","variables":{"slug":"' + $slug + '"},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"36b89d2507fce29e5ca551df756d27c1cfe079e2609642b4390aa4c35796eb11"}}}]'
            $r = Invoke-WebRequest -Uri $gqlUrl -Method POST -UseBasicParsing `
                -Headers @{ "Client-Id" = $clientId; "Content-Type" = "application/json" } `
                -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
            $d      = ($r.Content | ConvertFrom-Json)[0].data.clip
            $sig    = $d.playbackAccessToken.signature
            $token  = $d.playbackAccessToken.value
            $qs     = $d.videoQualities
            $srcUrl = ($qs | Where-Object { $_.quality -eq "1080" } | Select-Object -First 1).sourceURL
            if (-not $srcUrl) { $srcUrl = ($qs | Select-Object -First 1).sourceURL }
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
    }).AddArgument($slugs).AddArgument($cache).AddArgument($gqlUrl).AddArgument($clientId) | Out-Null
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

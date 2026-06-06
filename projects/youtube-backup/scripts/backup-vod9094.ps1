$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
$ytDlp = Join-Path $projectDir "tools\yt-dlp.exe"
$ffmpeg = Get-Command ffmpeg.exe -ErrorAction Stop
$ffmpegDir = Split-Path -Parent $ffmpeg.Source
$node = Get-Command node.exe -ErrorAction SilentlyContinue
$outDir = "I:\YT$([char]0x5f71)$([char]0x7247)$([char]0x5099)$([char]0x4efd)\vod9094"
$archive = Join-Path $outDir "download-archive.txt"
$channelUrl = "https://www.youtube.com/@vod9094/videos"

if (-not (Test-Path -LiteralPath $ytDlp)) {
    throw "yt-dlp.exe not found: $ytDlp"
}

if (-not (Test-Path -LiteralPath $ffmpegDir)) {
    throw "ffmpeg folder not found: $ffmpegDir"
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

& $ytDlp `
    --ffmpeg-location $ffmpegDir `
    --js-runtimes "node:$($node.Source)" `
    --ignore-errors `
    --continue `
    --no-overwrites `
    --windows-filenames `
    --download-archive $archive `
    --write-info-json `
    --write-thumbnail `
    --embed-thumbnail `
    --embed-metadata `
    --merge-output-format mp4 `
    -f "bv*+ba/b" `
    -o "$outDir\%(upload_date)s_%(title).150B [%(id)s].%(ext)s" `
    $channelUrl

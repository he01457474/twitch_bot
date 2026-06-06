$ErrorActionPreference = "Stop"

$outDir = "I:\YT$([char]0x5f71)$([char]0x7247)$([char]0x5099)$([char]0x4efd)\vod9094"
$archive = Join-Path $outDir "download-archive.txt"
$total = 165

while ($true) {
    Clear-Host

    $done = 0
    if (Test-Path -LiteralPath $archive) {
        $done = (Get-Content -LiteralPath $archive).Count
    }

    $percent = [math]::Floor(($done * 100) / $total)
    $mp4Count = (Get-ChildItem -LiteralPath $outDir -Filter "*.mp4" -File -ErrorAction SilentlyContinue).Count
    $partCount = (Get-ChildItem -LiteralPath $outDir -Filter "*.part" -File -ErrorAction SilentlyContinue).Count
    $running = [bool](Get-Process yt-dlp -ErrorAction SilentlyContinue)

    Write-Host "VOD9094 YouTube backup progress"
    Write-Host ""
    Write-Host "Folder: $outDir"
    Write-Host "Archive: $archive"
    Write-Host ""
    Write-Host "Completed: $done / $total"
    Write-Host "Progress : about $percent%"
    Write-Host "MP4 files: $mp4Count"
    Write-Host "Part temp: $partCount"
    Write-Host ""

    if ($done -ge $total) {
        Write-Host "Status: public and playlist backup finished."
        break
    }

    if (-not $running) {
        Write-Host "Status: yt-dlp is not running. Re-run the backup launcher to continue."
        break
    }

    Write-Host "Status: downloading."
    Write-Host ""
    Write-Host "Refreshes every 30 seconds. Closing this window will not stop yt-dlp."
    Start-Sleep -Seconds 30
}

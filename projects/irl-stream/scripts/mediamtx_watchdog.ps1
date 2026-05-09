param(
    [string]$ExePath,
    [string]$ConfigPath,
    [string]$WorkDir,
    [string]$PidFile
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 寫入自己的 PID 讓 stream_stop 能終止這個監控程序
[System.IO.File]::WriteAllText($PidFile, [System.Diagnostics.Process]::GetCurrentProcess().Id.ToString())

while ($true) {
    Start-Sleep -Seconds 30
    $proc = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
    if (-not $proc) {
        $ts = Get-Date -Format 'HH:mm:ss'
        Write-Host "[$ts] MediaMTX 已停止，正在重啟..." -ForegroundColor Yellow
        try {
            Start-Process -FilePath $ExePath -ArgumentList "`"$ConfigPath`"" -WorkingDirectory $WorkDir -WindowStyle Hidden
            Start-Sleep -Seconds 2
            $check = Get-Process 'mediamtx' -ErrorAction SilentlyContinue
            if ($check) {
                Write-Host "[$ts] MediaMTX 重啟成功" -ForegroundColor Green
            } else {
                Write-Host "[$ts] MediaMTX 重啟失敗，下次再試" -ForegroundColor Red
            }
        } catch {
            Write-Host "[$ts] 重啟時發生錯誤：$_" -ForegroundColor Red
        }
    }
}

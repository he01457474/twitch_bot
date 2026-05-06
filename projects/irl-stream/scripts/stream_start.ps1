# 管理員用：啟動 IRL 中繼伺服器環境
chcp 65001 | Out-Null

$sizeFile = Join-Path $PSScriptRoot "window_size.txt"

function Test-CommandAvailable {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Wait-DockerReady {
    param([int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "啟動 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，只負責本機中繼伺服器，不會啟動借用者的 NOALBS。" -ForegroundColor DarkGray

# [1/3] Docker Desktop
Write-Host "[1/3] 檢查 Docker Desktop..."
$dockerRunning = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) {
        Write-Host "[錯誤] 找不到 Docker Desktop：$dockerDesktop" -ForegroundColor Red
        Write-Host "請先安裝或手動開啟 Docker Desktop。" -ForegroundColor Yellow
        Read-Host "按 Enter 關閉"
        exit 1
    }
    Write-Host "開啟 Docker Desktop..."
    Start-Process $dockerDesktop
} else {
    Write-Host "Docker Desktop 已在執行" -ForegroundColor Green
}

if (-not (Test-CommandAvailable "docker")) {
    Write-Host "[錯誤] 找不到 docker 指令，請確認 Docker Desktop 已安裝完成。" -ForegroundColor Red
    Read-Host "按 Enter 關閉"
    exit 1
}

Write-Host "等待 Docker 可用..."
if (-not (Wait-DockerReady 60)) {
    Write-Host "[錯誤] Docker 還沒啟動完成，請稍後重試或手動檢查 Docker Desktop。" -ForegroundColor Red
    Read-Host "按 Enter 關閉"
    exit 1
}

# [2/3] mediamtx 容器
Write-Host "[2/3] 啟動 mediamtx 容器..."
$exists = docker ps -a --filter "name=^/mediamtx$" --format "{{.Names}}" 2>&1
if ($LASTEXITCODE -ne 0 -or $exists -notmatch "^mediamtx$") {
    Write-Host "[錯誤] 找不到名為 mediamtx 的 Docker 容器。" -ForegroundColor Red
    Write-Host "請先建立 MediaMTX 容器，或確認容器名稱是否還叫 mediamtx。" -ForegroundColor Yellow
    Read-Host "按 Enter 關閉"
    exit 1
}

docker start mediamtx 2>&1 | Out-Null
$running = docker ps --filter "name=^/mediamtx$" --filter "status=running" --format "{{.Names}}" 2>&1
if ($running -match "mediamtx") {
    Write-Host "mediamtx 啟動成功" -ForegroundColor Green
} else {
    Write-Host "[錯誤] mediamtx 啟動失敗，請手動檢查 Docker。" -ForegroundColor Red
    Read-Host "按 Enter 關閉"
    exit 1
}

# [3/3] No-IP DUC
Write-Host "[3/3] 檢查 No-IP DUC..."
$ducRunning = Get-Process "DUC40" -ErrorAction SilentlyContinue
if (-not $ducRunning) {
    $ducExe = "C:\Program Files (x86)\No-IP\DUC40.exe"
    if (Test-Path $ducExe) {
        Write-Host "啟動 No-IP DUC..."
        Start-Process $ducExe
    } else {
        Write-Host "[警告] 找不到 No-IP DUC：$ducExe" -ForegroundColor Yellow
        Write-Host "如果 DDNS 由其他方式維護，可以忽略這個警告。" -ForegroundColor DarkGray
    }
} else {
    Write-Host "No-IP DUC 已在執行" -ForegroundColor Green
}

Write-Host ""
Write-Host "中繼伺服器已啟動完成。" -ForegroundColor Cyan
Write-Host "借用者可以用 srt://flycat.ddns.net:5002 推流。" -ForegroundColor Cyan
Write-Host "借用者的 NOALBS 監測網址是 http://flycat.ddns.net:9997/v3/paths/get/<Twitch ID>。" -ForegroundColor Cyan
Write-Host "BRB 剪輯伺服器請另外用「啟動BRB伺服器.bat」開啟。" -ForegroundColor DarkGray
Read-Host "按 Enter 關閉"

# 儲存視窗大小（像素，不含位置）
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinSave {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc p, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr l);
    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }
    public static IntPtr Find(string t) {
        IntPtr f = IntPtr.Zero;
        EnumWindows((h, l) => {
            if (!IsWindowVisible(h)) return true;
            var s = new StringBuilder(512); GetWindowText(h, s, 512);
            if (s.ToString().IndexOf(t, StringComparison.OrdinalIgnoreCase) >= 0) { f = h; return false; }
            return true;
        }, IntPtr.Zero);
        return f;
    }
}
"@
$hwnd = [WinSave]::Find("StreamControl")
if ($hwnd -ne [IntPtr]::Zero) {
    $r = New-Object WinSave+RECT
    [WinSave]::GetWindowRect($hwnd, [ref]$r) | Out-Null
    "$($r.Right - $r.Left),$($r.Bottom - $r.Top)" | Set-Content $sizeFile
}

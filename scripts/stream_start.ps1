# 啟動StreamControl腳本
chcp 65001 | Out-Null

$sizeFile = "D:\tset\FlyCatClaude Code\scripts\window_size.txt"

Write-Host "啟動StreamControl..." -ForegroundColor Cyan

# [1/4] Docker Desktop
Write-Host "[1/4] 檢查 Docker Desktop..."
$dockerRunning = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerRunning) {
    Write-Host "開啟 Docker Desktop..."
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    Write-Host "等待 Docker 啟動，請稍候 20 秒..."
    Start-Sleep -Seconds 20
} else {
    Write-Host "Docker Desktop 已在執行" -ForegroundColor Green
}

# [2/4] mediamtx 容器
Write-Host "[2/4] 啟動 mediamtx 容器..."
docker start mediamtx 2>&1 | Out-Null
$running = docker ps --filter "name=mediamtx" --filter "status=running" --format "{{.Names}}" 2>&1
if ($running -match "mediamtx") {
    Write-Host "mediamtx 啟動成功" -ForegroundColor Green
} else {
    Write-Host "[警告] mediamtx 啟動失敗，請手動檢查 Docker" -ForegroundColor Yellow
}

# [3/4] No-IP DUC
Write-Host "[3/4] 檢查 No-IP DUC..."
$ducRunning = Get-Process "DUC40" -ErrorAction SilentlyContinue
if (-not $ducRunning) {
    Write-Host "啟動 No-IP DUC..."
    Start-Process "C:\Program Files (x86)\No-IP\DUC40.exe"
} else {
    Write-Host "No-IP DUC 已在執行" -ForegroundColor Green
}

# [4/5] NOALBS
Write-Host "[4/5] 啟動 NOALBS..."
$noalbsDir = "D:\tset\FlyCatClaude Code\tools\noalbs\noalbs-v2.16.1-x86_64-pc-windows-msvc"
$noalbsExe = "$noalbsDir\noalbs.exe"
Start-Process $noalbsExe -WorkingDirectory $noalbsDir -WindowStyle Hidden

# [5/5] BRB 伺服器
Write-Host "[5/5] 啟動 BRB 伺服器..."
$brbScript = "D:\tset\FlyCatClaude Code\scripts\brb_server.ps1"
Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -NoProfile -WindowStyle Hidden -File `"$brbScript`"" -WindowStyle Hidden
Write-Host "BRB 伺服器已啟動 (http://localhost:8080/brb-clips.html)" -ForegroundColor Green

Write-Host ""
Write-Host "全部啟動完成！記得開手機 IRL Pro。" -ForegroundColor Cyan
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

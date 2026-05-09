# 管理員用：啟動 IRL 中繼伺服器環境
chcp 65001 | Out-Null

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sizeFile = Join-Path $PSScriptRoot "window_size.txt"
$mediamtxDir = Join-Path $ProjectRoot "tools\mediamtx"
$mediamtxExe = Join-Path $mediamtxDir "mediamtx.exe"
$mediamtxConfig = Join-Path (Join-Path $ProjectRoot "config") "mediamtx.yml"
$whitelistScript = Join-Path $PSScriptRoot "manage_irl_users.ps1"

function Test-HttpOk {
    param([string]$Url)
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

Write-Host "啟動 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，只負責本機中繼伺服器，不會啟動借用者的 NOALBS。" -ForegroundColor DarkGray

# [1/2] MediaMTX 本機版
Write-Host "[1/2] 檢查 MediaMTX..."
if (-not (Test-Path $mediamtxExe)) {
    Write-Host "[錯誤] 找不到 MediaMTX 執行檔：" -ForegroundColor Red
    Write-Host "  $mediamtxExe" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "請下載 Windows 版 MediaMTX，解壓縮後把 mediamtx.exe 放到：" -ForegroundColor Yellow
    Write-Host "  $mediamtxDir" -ForegroundColor Yellow
    Read-Host "按 Enter 關閉"
    exit 1
}

if (Test-Path $whitelistScript) {
    Write-Host "套用 IRL 白名單設定..."
    & $whitelistScript -Mode Apply
} else {
    Write-Host "[警告] 找不到白名單管理腳本：$whitelistScript" -ForegroundColor Yellow
}

if (-not (Test-Path $mediamtxConfig)) {
    Write-Host "[錯誤] 找不到 MediaMTX 設定檔：" -ForegroundColor Red
    Write-Host "  $mediamtxConfig" -ForegroundColor Yellow
    Write-Host "請先用「管理IRL白名單.bat」新增台主，或確認白名單工具可正常套用。" -ForegroundColor Yellow
    Read-Host "按 Enter 關閉"
    exit 1
}

$mediamtxRunning = Get-Process "mediamtx" -ErrorAction SilentlyContinue
if ($mediamtxRunning) {
    Write-Host "MediaMTX 已在執行" -ForegroundColor Green
} else {
    Write-Host "啟動 MediaMTX 本機版..."
    Start-Process -FilePath $mediamtxExe -ArgumentList "`"$mediamtxConfig`"" -WorkingDirectory $mediamtxDir -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

if (Test-HttpOk "http://localhost:9997/v3/config/global/get") {
    Write-Host "MediaMTX API 已就緒：http://localhost:9997" -ForegroundColor Green
} else {
    Write-Host "[警告] MediaMTX 已啟動，但 API 尚未回應。" -ForegroundColor Yellow
    Write-Host "請確認 9997 port 沒被其他程式占用，或查看 MediaMTX 視窗 / log。" -ForegroundColor Yellow
}

$watchdogScript = Join-Path $PSScriptRoot "mediamtx_watchdog.ps1"
$watchdogPidFile = "$env:TEMP\mediamtx_watchdog.pid"
if (Test-Path $watchdogScript) {
    if (Test-Path $watchdogPidFile) {
        $oldPid = Get-Content $watchdogPidFile -ErrorAction SilentlyContinue
        if ($oldPid) { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
        Remove-Item $watchdogPidFile -ErrorAction SilentlyContinue
    }
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$watchdogScript`" -ExePath `"$mediamtxExe`" -ConfigPath `"$mediamtxConfig`" -WorkDir `"$mediamtxDir`" -PidFile `"$watchdogPidFile`"" -WindowStyle Hidden
    Write-Host "MediaMTX 監控已啟動（當機自動重啟）" -ForegroundColor Green
}

# [2/2] No-IP DUC
Write-Host "[2/2] 檢查 No-IP DUC..."
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
Write-Host "借用者的推流資料請用「管理IRL白名單.bat」新增台主後匯出。" -ForegroundColor Cyan
Write-Host "借用者的 NOALBS 監測網址是 http://flycat.ddns.net:9997/v3/paths/get/<Twitch ID>。" -ForegroundColor Cyan
Write-Host "SRTLA 之後會另外加 receiver；目前這個腳本先跑 SRT。" -ForegroundColor DarkGray
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

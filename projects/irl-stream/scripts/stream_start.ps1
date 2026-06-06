$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $PSScriptRoot "irl_settings.ps1")
$sizeFile = Join-Path $PSScriptRoot "window_size.txt"
$mediamtxDir = Join-Path $ProjectRoot "tools\mediamtx"
$mediamtxExe = Join-Path $mediamtxDir "mediamtx.exe"
$mediamtxConfig = Join-Path (Join-Path $ProjectRoot "config") "mediamtx.yml"
$whitelistScript = Join-Path $PSScriptRoot "manage_irl_users.ps1"
$dynuUpdateScript = Join-Path $PSScriptRoot "update_dynu_ddns.ps1"
$dynuWatchdogScript = Join-Path $PSScriptRoot "dynu_ddns_watchdog.ps1"
$dynuWatchdogPidFile = "$env:TEMP\dynu_ddns_watchdog.pid"
$pathWatchdogScript = Join-Path $PSScriptRoot "mediamtx_path_watchdog.ps1"
$pathWatchdogPidFile = "$env:TEMP\mediamtx_path_watchdog.pid"
$notifyScript = Join-Path $PSScriptRoot "send_irl_notification.ps1"
$relayHost = Get-IrlRelayHost
$publicSrtPort = 5002
$localSrtPort = 8890

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-HttpOk {
    param([string]$Url)
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Send-AdminNotification {
    param(
        [string]$Title,
        [string]$Message,
        [string]$Level = 'Info',
        [string]$Key = '',
        [int]$CooldownMinutes = 5
    )

    if (Test-Path $notifyScript) {
        & $notifyScript -Title $Title -Message $Message -Level $Level -Key $Key -CooldownMinutes $CooldownMinutes
    }
}

Write-Host "啟動 IRL 中繼伺服器環境..." -ForegroundColor Cyan
Write-Host "這是管理員端腳本，只負責本機中繼伺服器，不會啟動借用者的 NOALBS。" -ForegroundColor DarkGray
if (Test-IsAdministrator) {
    Write-Host "[提醒] 目前是系統管理員權限。初始化和防火牆設定需要管理員；平常啟動伺服器建議用一般雙擊即可。" -ForegroundColor Yellow
}

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

# [2/2] Dynu DDNS
Write-Host "[2/2] 更新 Dynu DDNS..."
if (Test-Path $dynuUpdateScript) {
    try {
        & $dynuUpdateScript
    } catch {
        Write-Host "[警告] Dynu 更新失敗：$($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "中繼伺服器仍會繼續啟動；請稍後檢查「設定DynuDDNS.bat」。" -ForegroundColor DarkGray
        Send-AdminNotification -Title 'Dynu DDNS 更新失敗' -Message $_.Exception.Message -Level Error -Key 'dynu-update-failed' -CooldownMinutes 10
    }
} else {
    Write-Host "[警告] 找不到 Dynu 更新腳本：$dynuUpdateScript" -ForegroundColor Yellow
}

if (Test-Path $dynuWatchdogScript) {
    if (Test-Path $dynuWatchdogPidFile) {
        $oldPid = Get-Content $dynuWatchdogPidFile -ErrorAction SilentlyContinue
        if ($oldPid) { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
        Remove-Item $dynuWatchdogPidFile -ErrorAction SilentlyContinue
    }
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$dynuWatchdogScript`" -PidFile `"$dynuWatchdogPidFile`"" -WindowStyle Hidden
    Write-Host "Dynu DDNS 監控已啟動（每 5 分鐘自動更新）" -ForegroundColor Green
}

if (Test-Path $pathWatchdogScript) {
    if (Test-Path $pathWatchdogPidFile) {
        $oldPid = Get-Content $pathWatchdogPidFile -ErrorAction SilentlyContinue
        if ($oldPid -and $oldPid -match '^\d+$') { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
        Remove-Item $pathWatchdogPidFile -ErrorAction SilentlyContinue
    }
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$pathWatchdogScript`" -PidFile `"$pathWatchdogPidFile`"" -WindowStyle Hidden
    Write-Host "台主推流監控已啟動（開始 / 停止推流通知管理員）" -ForegroundColor Green
}

# Discord 指令監聽（背景，收到 /狀態 就查狀態）
$discordBotScript = Join-Path $PSScriptRoot "irl_discord_bot.py"
$discordEnvFile = Join-Path $ProjectRoot ".env"
$discordBotPidFile = "$env:TEMP\irl_discord_bot.pid"
$discordToken = ''
$discordPython = 'pythonw'
if (Test-Path $discordEnvFile) {
    foreach ($line in (Get-Content -LiteralPath $discordEnvFile -Encoding UTF8)) {
        if ($line -match '^\s*IRL_DISCORD_TOKEN\s*=\s*(.+)$') { $discordToken = $matches[1].Trim() }
        elseif ($line -match '^\s*IRL_PYTHON_PATH\s*=\s*(.+)$') { $discordPython = $matches[1].Trim() }
    }
}
if ((Test-Path $discordBotScript) -and $discordToken) {
    if (Test-Path $discordBotPidFile) {
        $oldPid = Get-Content $discordBotPidFile -ErrorAction SilentlyContinue
        if ($oldPid -and $oldPid -match '^\d+$') { Stop-Process -Id ([int]$oldPid) -Force -ErrorAction SilentlyContinue }
        Remove-Item $discordBotPidFile -ErrorAction SilentlyContinue
    }
    try {
        Start-Process -FilePath $discordPython -ArgumentList "`"$discordBotScript`"" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
        Write-Host "Discord 指令監聽已啟動（在 Discord 打 /狀態 查狀態）" -ForegroundColor Green
    } catch {
        Write-Host "[警告] Discord 指令監聽啟動失敗：$($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "請確認筆電已安裝 Python 與 discord.py。" -ForegroundColor DarkGray
    }
} elseif (Test-Path $discordBotScript) {
    Write-Host "Discord 指令監聽未設定（.env 沒有 IRL_DISCORD_TOKEN），略過。可用「設定Discord指令.bat」設定。" -ForegroundColor DarkGray
}

Send-AdminNotification -Title 'IRL 中繼伺服器已啟動' -Message "對外網址：srt://${relayHost}:$publicSrtPort`n本機 SRT：:$localSrtPort" -Level Success -Key 'relay-started' -CooldownMinutes 1

Write-Host ""
Write-Host "中繼伺服器已啟動完成。" -ForegroundColor Cyan
Write-Host "借用者的推流資料請用「管理IRL白名單.bat」新增台主後匯出。" -ForegroundColor Cyan
Write-Host "目前對外網址：srt://${relayHost}:$publicSrtPort" -ForegroundColor Cyan
Write-Host "管理員本機 OBS 測試：srt://127.0.0.1:$localSrtPort?streamid=read:<Twitch ID>:<read user>:<read key>" -ForegroundColor Cyan
Write-Host "目前網路轉發架構：數據機 UDP $publicSrtPort -> Deco UDP $publicSrtPort -> 本機 UDP $localSrtPort" -ForegroundColor DarkGray
Write-Host "借用者的 NOALBS 監測網址是 http://${relayHost}:9997/v3/paths/get/<Twitch ID>。" -ForegroundColor Cyan
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

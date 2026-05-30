$ErrorActionPreference = "SilentlyContinue"

$downloadDirName = -join ([char]0x4e0b, [char]0x8f09)
$botRoot = "D:\$downloadDirName\BOT2"
$repoRoot = Join-Path $botRoot "repo_temp"
$chromeProfileRoot = Join-Path $repoRoot "src\.chrome_profiles"
$privateRoot = "D:\tset\bot_private"
$knownRoots = @($botRoot, $repoRoot, $privateRoot, $chromeProfileRoot) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

function Write-Step {
    param([string]$Message)
    Write-Host "[force-stop] $Message"
}

function Test-BotCommandLine {
    param([string]$CommandLine)
    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $false
    }

    $normalized = $CommandLine.ToLowerInvariant().Replace("/", "\")
    if ($normalized -notlike "*test.py*" -and $normalized -notlike "*start_bot.bat*") {
        return $false
    }

    foreach ($root in $knownRoots) {
        $rootNorm = $root.ToLowerInvariant().Replace("/", "\")
        if ($normalized.Contains($rootNorm)) {
            return $true
        }
    }

    return $false
}

function Test-BotBrowserCommandLine {
    param([string]$CommandLine)
    if ([string]::IsNullOrWhiteSpace($CommandLine)) {
        return $false
    }

    $normalized = $CommandLine.ToLowerInvariant().Replace("/", "\")
    if ($normalized -notlike "*chrome*" -and $normalized -notlike "*chromedriver*") {
        return $false
    }

    if ($normalized -like "*\.chrome_profiles\*" -or $normalized -like "*--user-data-dir=*\.chrome_profiles*") {
        return $true
    }

    foreach ($root in $knownRoots) {
        $rootNorm = $root.ToLowerInvariant().Replace("/", "\")
        if ($normalized.Contains($rootNorm)) {
            return $true
        }
    }

    return $false
}

function Stop-Tree {
    param([int]$ProcessId, [string]$Reason)
    if ($ProcessId -le 0 -or $ProcessId -eq $PID) {
        return
    }

    Write-Step "Stopping PID $ProcessId ($Reason)"
    & taskkill.exe /T /F /PID $ProcessId 2>$null | Out-Null
}

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public class FlyCatBotWindowTools {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc proc, IntPtr lp);
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hwnd, StringBuilder sb, int len);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")]
    public static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam);

    public delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lp);

    public static IntPtr[] FindByTitle(string part) {
        var found = new System.Collections.Generic.List<IntPtr>();
        EnumWindows((hwnd, lp) => {
            if (!IsWindowVisible(hwnd)) return true;
            var sb = new StringBuilder(512);
            GetWindowText(hwnd, sb, 512);
            if (sb.ToString().IndexOf(part, StringComparison.OrdinalIgnoreCase) >= 0) {
                found.Add(hwnd);
            }
            return true;
        }, IntPtr.Zero);
        return found.ToArray();
    }
}
"@

function Close-BotWindows {
    $wmClose = 0x0010
    $hwndFile = Join-Path $env:TEMP "botwinhwnd.txt"
    $targets = New-Object System.Collections.Generic.List[IntPtr]

    if (Test-Path -LiteralPath $hwndFile) {
        $raw = Get-Content -LiteralPath $hwndFile | Select-Object -First 1
        $parsed = 0L
        if ([long]::TryParse($raw, [ref]$parsed)) {
            $candidate = [IntPtr]$parsed
            if ([FlyCatBotWindowTools]::IsWindow($candidate)) {
                $targets.Add($candidate)
            }
        }
    }

    foreach ($hwnd in [FlyCatBotWindowTools]::FindByTitle("FlyCat Bot")) {
        if (-not $targets.Contains($hwnd)) {
            $targets.Add($hwnd)
        }
    }

    foreach ($hwnd in $targets) {
        [FlyCatBotWindowTools]::PostMessage($hwnd, $wmClose, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
    }
}

Write-Step "Closing FlyCat Bot windows"
Close-BotWindows
Start-Sleep -Milliseconds 700

$pidFiles = @(
    (Join-Path $botRoot "bot.pid"),
    (Join-Path $repoRoot "bot.pid")
)

foreach ($pidFile in $pidFiles) {
    if (Test-Path -LiteralPath $pidFile) {
        $rawPid = Get-Content -LiteralPath $pidFile | Select-Object -First 1
        $botPid = 0
        if ([int]::TryParse($rawPid, [ref]$botPid)) {
            Stop-Tree -ProcessId $botPid -Reason "pid file"
        }
        Remove-Item -LiteralPath $pidFile -Force
    }
}

$processes = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and
    ($_.Name -match "^(python|pythonw|py|cmd)\.exe$") -and
    (Test-BotCommandLine $_.CommandLine)
}

foreach ($proc in $processes) {
    Stop-Tree -ProcessId ([int]$proc.ProcessId) -Reason $proc.Name
}

Start-Sleep -Milliseconds 700

$browserProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and
    ($_.Name -match "^(chrome|chromedriver)\.exe$") -and
    (Test-BotBrowserCommandLine $_.CommandLine)
}

foreach ($proc in $browserProcesses) {
    Stop-Tree -ProcessId ([int]$proc.ProcessId) -Reason "BOT browser"
}

Start-Sleep -Milliseconds 700
Close-BotWindows

$flagFiles = @(
    (Join-Path $botRoot "bot_updating.flag"),
    (Join-Path $repoRoot "bot_updating.flag")
)

foreach ($flagFile in $flagFiles) {
    if (Test-Path -LiteralPath $flagFile) {
        Remove-Item -LiteralPath $flagFile -Force
    }
}

Write-Step "Finished"

param([string]$Title = "StreamControl")
$sizeFile = "D:\tset\FlyCatClaude Code\scripts\window_size.txt"
if (-not (Test-Path $sizeFile)) { exit }

$parts = (Get-Content $sizeFile) -split ","
$w, $h = [int]$parts[0], [int]$parts[1]

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinRestore {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc p, IntPtr l);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool rep);
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

$timeout = (Get-Date).AddSeconds(10)
while ((Get-Date) -lt $timeout) {
    $hwnd = [WinRestore]::Find($Title)
    if ($hwnd -ne [IntPtr]::Zero) {
        Start-Sleep -Milliseconds 500
        $r = New-Object WinRestore+RECT
        [WinRestore]::GetWindowRect($hwnd, [ref]$r) | Out-Null
        [WinRestore]::MoveWindow($hwnd, $r.Left, $r.Top, $w, $h, $true) | Out-Null
        exit
    }
    Start-Sleep -Milliseconds 300
}

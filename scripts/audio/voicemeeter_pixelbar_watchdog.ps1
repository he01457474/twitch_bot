[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$logFile = "$env:TEMP\vmwatchdog.log"
function Write-Log($msg, $color = "White") {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Host $line -ForegroundColor $color
}

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class VBVMR {
    const string DLL = @"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll";
    [DllImport(DLL)] public static extern int VBVMR_Login();
    [DllImport(DLL)] public static extern int VBVMR_Logout();
    [DllImport(DLL)] public static extern int VBVMR_IsParametersDirty();
    [DllImport(DLL)] public static extern int VBVMR_GetParameterFloat([MarshalAs(UnmanagedType.LPStr)] string paramName, out float value);
    [DllImport(DLL, CharSet=CharSet.Ansi)] public static extern int VBVMR_SetParameters([MarshalAs(UnmanagedType.LPStr)] string param);
}
"@

$ret = [VBVMR]::VBVMR_Login()
if ($ret -ne 0 -and $ret -ne 1) {
    Write-Log "無法連線 VoiceMeeter（錯誤碼 $ret），請確認 VoiceMeeter 已開啟。" "Red"
    Start-Sleep 5
    exit 1
}
Write-Log "已連線 VoiceMeeter，監控 PixelBar (A3) Mute 狀態..." "Green"

$wasMuted = $null

try {
    while ($true) {
        $dirty = [VBVMR]::VBVMR_IsParametersDirty()
        if ($dirty -gt 0) {
            $muteVal = [float]0
            [VBVMR]::VBVMR_GetParameterFloat("Bus[2].Mute", [ref]$muteVal) | Out-Null
            $isMuted = $muteVal -gt 0.5

            if ($wasMuted -eq $true -and -not $isMuted) {
                Write-Log "偵測到 PixelBar 解除靜音，重置 Audio Engine..." "Cyan"
                Start-Sleep -Milliseconds 500
                [VBVMR]::VBVMR_SetParameters("Command.Restart=1;") | Out-Null
                Write-Log "Audio Engine 已重置。" "Green"
            }
            $wasMuted = $isMuted
        }
        Start-Sleep -Milliseconds 300
    }
} finally {
    [VBVMR]::VBVMR_Logout() | Out-Null
}

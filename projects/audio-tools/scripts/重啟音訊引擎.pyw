import ctypes, time, subprocess

DLL_PATH = r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll"

def notify(title, msg):
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
         f"Add-Type -AssemblyName System.Windows.Forms; "
         f"$n=New-Object System.Windows.Forms.NotifyIcon; "
         f"$n.Icon=[System.Drawing.SystemIcons]::Information; "
         f"$n.Visible=$true; "
         f"$n.ShowBalloonTip(3000,'{title}','{msg}',[System.Windows.Forms.ToolTipIcon]::Info); "
         f"Start-Sleep 4; $n.Dispose()"],
        creationflags=0x08000000
    )

try:
    vmr = ctypes.windll.LoadLibrary(DLL_PATH)
    if vmr.VBVMR_Login() < 0:
        notify("音訊引擎", "無法連接 VoiceMeeter，請確認程式是否開啟")
    else:
        time.sleep(0.2)
        vmr.VBVMR_SetParameterFloat(b"Command.Restart", ctypes.c_float(1))
        time.sleep(0.3)
        vmr.VBVMR_Logout()
        notify("音訊引擎", "音訊引擎已重啟")
except Exception as e:
    notify("音訊引擎", f"錯誤：{e}")

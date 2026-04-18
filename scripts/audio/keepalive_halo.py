"""
Halo PixelBar 保活腳本
直接對 Halo PixelBar 送極低音量信號，繞過 VoiceMeeter，防止喇叭進入休眠。
"""
import sounddevice as sd
import numpy as np
import time
import sys

SAMPLE_RATE = 48000
AMPLITUDE   = 0.0005   # -66dB，完全聽不到
DURATION    = 0.3      # 每次送 0.3 秒
INTERVAL    = 8        # 每 8 秒送一次

def find_halo():
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if 'Halo PixelBar' in d['name'] and d['max_output_channels'] > 0:
            return i, d['name']
    return None, None

device_id, device_name = find_halo()
if device_id is None:
    print("找不到 Halo PixelBar，請確認喇叭已插上")
    time.sleep(5)
    sys.exit(1)

print(f"保活目標：{device_name}（device {device_id}）")
print(f"每 {INTERVAL} 秒送一次無聲信號，Ctrl+C 停止")

t      = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), dtype=np.float32)
signal = (AMPLITUDE * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

while True:
    try:
        sd.play(signal, samplerate=SAMPLE_RATE, device=device_id, blocking=True)
    except Exception as e:
        print(f"[警告] {e}")
    time.sleep(INTERVAL)

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import json
import os
import sys
import ctypes
import colorsys
import win32gui
import win32api
import win32ui
import win32con
from PIL import Image, ImageTk, ImageChops, ImageStat

# 隱藏 CMD 視窗
try:
    hwnd_con = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd_con:
        ctypes.windll.user32.ShowWindow(hwnd_con, 0)
except Exception:
    pass

MOLE_W = 960
MOLE_H = 560

# 打包成 exe 後 __file__ 指向暫存目錄，改用 sys.executable 所在目錄
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(_APP_DIR, "restaurant_config.json")

# 預設值
DEFAULT_STOVES = [
    (175, 215), (175, 265), (175, 315),
    (785, 215), (785, 265), (785, 315),
]
DEFAULT_RECIPE = {
    "left_arrow":  (250, 480),
    "right_arrow": (710, 480),
    "close":       (733, 110),
    "page_tabs":   [(345,480),(395,480),(445,480),(495,480),(545,480)],
    "dishes":      [(345,245),(490,245),(635,245),(345,385),(490,385),(635,385)],
    "check_pt":    (550, 160),   # 食譜標題區偵測點
    "confirm_btn": (395, 415),   # 捐菜彈窗的「確認」按鈕（清除腐壞食物）
    "cancel_btn":  (540, 415),   # 捐菜彈窗的「取消」按鈕（做菜中，不打擾）
}
DEFAULT_SETTINGS = {
    "page": 6, "dish": 1, "cook_minutes": 20, "cook_seconds": 0,
    "antlag_minutes": 5,
    "harvest_wait": 3,         # 收菜後等待秒數，再重新點鍋爐
    "restart_wait_seconds": 15, # 視窗消失後等待重新出現的秒數
    "restaurant_pt":    None,  # 餐廳確認點座標（靜態固定顏色，用來判斷是否在餐廳內）
    "restaurant_color": None,  # 餐廳確認點顏色
    "door_out":      None,  # 出門座標（餐廳內往外走的門口）
    "door_waypoint": None,  # 出門後走到入口前的中途路徑點（選填）
    "door_in":       None,  # 進門座標（餐廳外往內走的門口）
    "spoiled_color":  None,   # 腐壞（舊格式，單點）
    "spoiled_offset": None,
    "clock_color":   None,    # 時鐘（舊格式，單點）
    "clock_offset":  None,
    "done_color":    None,    # 做完（舊格式，單點）
    "done_offset":   None,
    # 多點格式（新，優先使用）：每個元素 = [dx, dy, r, g, b]
    "done_points":    [],
    "clock_points":   [],
    "spoiled_points": [],
    "state_threshold": 40,    # 顏色差異容許值
    # HSV 區域偵測（新格式，每個元素對應一個鍋爐）
    # 格式：{"cx":dx, "cy":dy, "radius":10, "h":[hmin,hmax], "s":[smin,smax], "v":[vmin,vmax], "pct":0.15}
    "done_hsv_list":    [],
    "clock_hsv_list":   [],
    "spoiled_hsv_list": [],
    # 時鐘內部偵測：各爐獨立偏移 [dx,dy]，指向橙色環內側
    # 掃描白色像素（白色扇形 = 剩餘時間），區分烹飪中 vs 菜做好
    "clock_interior_offsets": [],
    "cooking_white_threshold": 0.10,  # 白色 pct 超過此值 → 烹飪中（有白色扇形）
    "done_white_threshold":    0.05,  # 白色 pct 低於此值 → 菜做好（時鐘滿了）
    "recipe_open_timeout":     1.4,
    "progress_start_timeout":  0.65,
    "progress_gone_misses":    2,
    # 黑煙偵測（方案 B）：相對各鍋爐中心的偏移 [dx,dy]，清單長度 = 鍋爐數
    # 若清單為空則 fallback 到 HSV 腐壞偵測
    "smoke_offsets":      [],
    "smoke_threshold":    30,    # 暗色像素 V < 此值視為黑煙（0~100）
    "smoke_pct_threshold": 0.15, # 暗色像素佔比超過此值 → 有黑煙
    # 重連 / 閃退設定
    "flash_exe_path": "",
    "game_url":       "http://mole.61.com.tw/Client.swf",
    # 各畫面按鈕座標（遊戲 960×560 坐標系）
    "btn_disconnect_confirm": [478, 382],  # 斷線「確認」按鈕
    "btn_notice_ok":          [480, 390],  # system notice ok
    "btn_online_time_ok":     [480, 410],  # online time notice ok
    "btn_game_start":         [484, 398],  # 主畫面「開始」
    "btn_login":              [484, 432],  # 角色選擇「登入」
    "btn_quick_start":        [456, 517],  # 選伺服器「快速開始」
    "btn_happy_spin_close":   [705, 105],  # 歡樂轉轉彈窗關閉
    "btn_land":               [880, 538],  # 遊戲內右下角「地盤」
    "btn_land_restaurant":    [880, 449],  # 地盤選單 / 場景中的「餐廳」
}
MAP_BTN        = (33,  505)
HOME_BTN       = (880, 538)
RESTAURANT_BTN = (880, 449)


# ── 設定讀寫 ──────────────────────────────────────────

def load_config():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    stoves = [tuple(s) for s in data.get("stoves", DEFAULT_STOVES)]

    r = data.get("recipe", {})
    recipe = {
        "left_arrow":  tuple(r.get("left_arrow",  DEFAULT_RECIPE["left_arrow"])),
        "right_arrow": tuple(r.get("right_arrow", DEFAULT_RECIPE["right_arrow"])),
        "close":       tuple(r.get("close",        DEFAULT_RECIPE["close"])),
        "page_tabs":   [tuple(t) for t in r.get("page_tabs", DEFAULT_RECIPE["page_tabs"])],
        "dishes":      [tuple(d) for d in r.get("dishes",    DEFAULT_RECIPE["dishes"])],
        "check_pt":    tuple(r.get("check_pt",    DEFAULT_RECIPE["check_pt"])),
        "confirm_btn": tuple(r.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])),
        "cancel_btn":  tuple(r.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"])),
    }

    s = data.get("settings", {})
    settings = {k: s.get(k, DEFAULT_SETTINGS[k]) for k in DEFAULT_SETTINGS}

    return stoves, recipe, settings


def save_config(stoves, recipe, settings):
    payload = {"stoves": stoves, "recipe": recipe, "settings": settings}
    tmp_file = CONFIG_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_file, CONFIG_FILE)


# ── 截圖 ─────────────────────────────────────────────

def capture_window(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    w, h = rect[2], rect[3]
    # 用 GetDC 取 client area DC，和 click() 的座標系一致
    hwndDC = win32gui.GetDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    bmp    = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    info = bmp.GetInfo()
    raw  = bmp.GetBitmapBits(True)
    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC(); mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), raw, "raw", "BGRX", 0, 1)
    return img, w, h


# ── HSV 區域偵測輔助 ──────────────────────────────────

def _rgb_to_hsv(r, g, b):
    """RGB (0-255) → HSV (h: 0-360, s: 0-100, v: 0-100)"""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return h * 360, s * 100, v * 100


def _hsv_match_pct(img, scale, mole_cx, mole_cy, radius, h_range, s_range, v_range):
    """
    以 (mole_cx, mole_cy) 為中心、radius 為半徑的方形區域內，
    計算符合 HSV 範圍的像素佔比（0.0 ~ 1.0）。
    h_range = [hmin, hmax]（支援跨 0 的紅色系，例如 [350, 10]）
    """
    w, h_img = img.size
    total = matched = 0
    hmin, hmax = h_range
    smin, smax = s_range
    vmin, vmax = v_range
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            px = min(max(int((mole_cx + dx) * scale), 0), w - 1)
            py = min(max(int((mole_cy + dy) * scale), 0), h_img - 1)
            r2, g2, b2 = img.getpixel((px, py))
            hh, ss, vv = _rgb_to_hsv(r2, g2, b2)
            total += 1
            h_ok = (hmin <= hh <= hmax) if hmin <= hmax else (hh >= hmin or hh <= hmax)
            if h_ok and smin <= ss <= smax and vmin <= vv <= vmax:
                matched += 1
    return matched / total if total > 0 else 0.0


def _hsv_color_name(h, s, v):
    """把 HSV 值轉成中文顏色名稱，方便使用者判斷。"""
    if v < 20:              return "黑色"
    if s < 15:              return "白/灰色"
    if h < 15 or h >= 345: return "紅色"
    if h < 45:              return "橙色"
    if h < 75:              return "黃色"
    if h < 150:             return "綠色"
    if h < 195:             return "青色"
    if h < 255:             return "藍色"
    if h < 285:             return "紫色"
    return "粉紅色"


# 每個狀態的預期顏色範圍（用於校準時給使用者提示）
_STATE_COLOR_HINTS = {
    "clock_offset": {
        "label":  "時鐘（烹飪中）",
        "expect": "橙色（H 10-50°，飽和度 > 55%，亮度 > 45%）",
        "check":  lambda h, s, v: 10 <= h <= 50 and s >= 55 and v >= 45,
    },
    "done_offset": {
        "label":  "做完（黃光）",
        "expect": "黃色（H 35-75°，飽和度 > 35%，亮度 > 55%）",
        "check":  lambda h, s, v: 35 <= h <= 75 and s >= 35 and v >= 55,
    },
    "spoiled_offset": {
        "label":  "腐壞（黑煙）",
        "expect": "深色/灰色（亮度 < 50%，或飽和度低）",
        "check":  lambda h, s, v: v <= 50 or (s <= 30 and v <= 65),
    },
}


def _sample_hsv_range(img_rgb, px_x, px_y, sample_r=5):
    """
    取樣 (px_x, px_y) 附近 sample_r 半徑的方形區域，
    計算 HSV 均值並建議範圍（mean ± tolerance）。
    回傳 dict: {"h", "s", "v", "radius", "pct", "cx":0, "cy":0}
    """
    w, h = img_rgb.size
    hs, ss, vs = [], [], []
    for dy in range(-sample_r, sample_r + 1):
        for dx in range(-sample_r, sample_r + 1):
            ix = min(max(px_x + dx, 0), w - 1)
            iy = min(max(px_y + dy, 0), h - 1)
            r, g, b = img_rgb.getpixel((ix, iy))
            hh, s2, vv = _rgb_to_hsv(r, g, b)
            hs.append(hh); ss.append(s2); vs.append(vv)
    nm = len(hs)
    h_mean = sum(hs) / nm
    s_mean = sum(ss) / nm
    v_mean = sum(vs) / nm
    h_std  = (sum((x - h_mean) ** 2 for x in hs) / nm) ** 0.5
    s_std  = (sum((x - s_mean) ** 2 for x in ss) / nm) ** 0.5
    v_std  = (sum((x - v_mean) ** 2 for x in vs) / nm) ** 0.5
    H_TOL = max(h_std * 2.5, 20)
    S_TOL = max(s_std * 2.5, 28)
    V_TOL = max(v_std * 2.5, 28)
    return {
        "cx": 0, "cy": 0,
        "radius": 10,
        "h": [round(max(h_mean - H_TOL, 0), 1),  round(min(h_mean + H_TOL, 360), 1)],
        "s": [round(max(s_mean - S_TOL, 0), 1),  round(min(s_mean + S_TOL, 100), 1)],
        "v": [round(max(v_mean - V_TOL, 0), 1),  round(min(v_mean + V_TOL, 100), 1)],
        "pct": 0.12,
    }


# ── 校準視窗（通用）──────────────────────────────────

class CalibrationWindow:
    """
    prompts: list[str]  每次點擊對應的說明文字
    on_done: callable(list[(mole_x, mole_y)])
    """
    def __init__(self, parent, hwnd, prompts, on_done):
        self.hwnd    = hwnd
        self.prompts = prompts
        self.on_done = on_done
        self.clicks  = []
        self.display_scale = 1.0

        self.win = tk.Toplevel(parent)
        self.win.title("座標校準")
        self.win.grab_set()
        self._build()

    def _build(self):
        ttk.Label(self.win,
                  text=f"依序點擊，共 {len(self.prompts)} 個點（點完自動關閉）",
                  padding=8).pack()
        self.info = ttk.Label(self.win,
                              text=f"▶ {self.prompts[0]}",
                              foreground="blue", padding=4)
        self.info.pack()

        try:
            img, game_w, game_h = capture_window(self.hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}", parent=self.win)
            self.win.destroy()
            return

        self.game_w, self.game_h = game_w, game_h
        scale = min(900 / game_w, 580 / game_h, 1.0)
        self.display_scale = scale
        disp = img.resize((int(game_w * scale), int(game_h * scale)))
        self.photo = ImageTk.PhotoImage(disp)

        self.canvas = tk.Canvas(self.win,
                                width=int(game_w * scale),
                                height=int(game_h * scale),
                                cursor="crosshair")
        self.canvas.pack(padx=8, pady=8)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.bind("<Button-1>", self._on_click)

    def _on_click(self, event):
        sg = max(self.game_w / MOLE_W, self.game_h / MOLE_H)
        mx = int((event.x / self.display_scale) / sg)
        my = int((event.y / self.display_scale) / sg)
        self.clicks.append((mx, my))
        n = len(self.clicks)

        r = 6
        self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r,
                                fill="red", outline="white", width=2)
        self.canvas.create_text(event.x+12, event.y, text=str(n),
                                fill="red", font=("Arial", 10, "bold"))

        if n < len(self.prompts):
            self.info.config(text=f"▶ {self.prompts[n]}")
        else:
            self.info.config(text="✔ 完成！")
            self.win.after(600, self._finish)

    def _finish(self):
        self.on_done(self.clicks)
        self.win.destroy()


# ── 機器人邏輯 ────────────────────────────────────────

DEBUG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")
LIVE_SNAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug", "bot_live.png")

class RestaurantBot:
    def __init__(self, stoves, recipe, settings):
        self.hwnd     = None
        self._stop    = threading.Event()
        self.stoves   = stoves
        self.recipe   = recipe
        self.settings = settings
        self._recipe_closed_baseline = None   # 食譜關閉時的 check_pt 顏色基準
        self._debug   = False                 # Debug 模式：存標記截圖
        self._last_antlag = 0.0               # 上次執行防卡頓的時間戳記
        self._last_popup_img  = None           # 最近一次彈窗截圖（RAM，程式結束自動清除）
        self._last_ocr_text   = ""             # 最近一次 OCR 辨識文字（供 log 顯示）

    def _debug_capture(self, label, markers=None):
        """
        存一張標記截圖到 debug/ 資料夾。
        markers: list of (mole_x, mole_y, outline_color, text)
        """
        if not self._debug or not self.hwnd:
            return
        try:
            from PIL import ImageDraw
            img, w, h = capture_window(self.hwnd)
            scale = max(w / MOLE_W, h / MOLE_H)
            draw  = ImageDraw.Draw(img)
            for mx, my, color, text in (markers or []):
                px, py = int(mx * scale), int(my * scale)
                r = 9
                draw.ellipse([px-r, py-r, px+r, py+r], outline=color, width=3)
                draw.text((px + r + 3, py - 8), text, fill=color)
            os.makedirs(DEBUG_DIR, exist_ok=True)
            fname = f"{time.strftime('%H%M%S')}_{label}.png"
            img.save(os.path.join(DEBUG_DIR, fname))
        except Exception:
            pass

    # ── OCR 彈窗偵測 ──────────────────────────────────────────────────────

    def _capture_popup_region(self):
        """截取彈窗文字區，存到 self._last_popup_img 並回傳 PIL Image。
        取 confirm_btn 上方的矩形區域，涵蓋兩行彈窗說明文字。"""
        if not self.hwnd:
            return None
        try:
            img, w, h = capture_window(self.hwnd)
            img   = img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)

            confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
            cancel_btn  = self.recipe.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"])

            # 彈窗文字在按鈕上方 ~20-170px（mole 座標）
            # 往上多留 60px（改為 170），確保兩行文字都能截到
            left  = max(0, int((min(confirm_btn[0], cancel_btn[0]) - 160) * scale))
            right = min(w, int((max(confirm_btn[0], cancel_btn[0]) + 160) * scale))
            top   = max(0, int((confirm_btn[1] - 170) * scale))
            bot   = min(h, int((confirm_btn[1] -  15) * scale))

            region = img.crop((left, top, right, bot))
            self._last_popup_img = region
            return region
        except Exception:
            return None

    def _ocr_image(self, pil_img):
        """用 Windows 內建 OCR 辨識 PIL Image，回傳文字字串。
        透過 subprocess 執行，避免 worker thread COM apartment 衝突。
        需要 winsdk 套件（pip install winsdk）；未安裝時回傳空字串。"""
        _OCR_SCRIPT = r"""
import sys, asyncio, io
sys.stdout.reconfigure(encoding='utf-8')
import winsdk.windows.media.ocr as ocr
import winsdk.windows.globalization as glob
import winsdk.windows.graphics.imaging as wgi
import winsdk.windows.storage.streams as wss

async def run():
    data = sys.stdin.buffer.read()
    stream = wss.InMemoryRandomAccessStream()
    writer = wss.DataWriter(stream)
    writer.write_bytes(data)
    await writer.store_async()
    stream.seek(0)
    decoder = await wgi.BitmapDecoder.create_async(stream)
    bitmap  = await decoder.get_software_bitmap_async()
    if bitmap.bitmap_pixel_format != wgi.BitmapPixelFormat.BGRA8:
        bitmap = wgi.SoftwareBitmap.convert(bitmap, wgi.BitmapPixelFormat.BGRA8)
    for tag in ['zh-Hans-CN', 'zh-TW']:
        lang = glob.Language(tag)
        if ocr.OcrEngine.is_language_supported(lang):
            engine = ocr.OcrEngine.try_create_from_language(lang)
            if engine:
                result = await engine.recognize_async(bitmap)
                print(result.text if result else '', end='')
                return

asyncio.run(run())
"""
        try:
            import subprocess, io, sys
            buf = io.BytesIO()
            pil_img.convert("RGB").save(buf, format="PNG")
            result = subprocess.run(
                [sys.executable, "-c", _OCR_SCRIPT],
                input=buf.getvalue(),
                capture_output=True,
                timeout=10,
            )
            return result.stdout.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def _detect_popup_type(self):
        """截圖彈窗文字區 → OCR → 判斷彈窗類型。
        回傳：'spoiled'（燒糊）、'donation'（捐菜）、None（無法判斷）
        辨識結果同時存到 self._last_ocr_text 供外部 log。"""
        region = self._capture_popup_region()
        if region is None:
            self._last_ocr_text = ""
            return None
        text = self._ocr_image(region)
        self._last_ocr_text = text.strip()
        if not text:
            return None
        if any(kw in text for kw in [
            "\u71d2\u7cca", "\u70e7\u7cca", "\u71d2\u58de", "\u70e7\u574f",
            "\u8150\u58de", "\u8150\u574f", "\u8655\u7406", "\u5904\u7406",
        ]):
            return "spoiled"
        if any(kw in text for kw in [
            "\u6350", "\u6d41\u6d6a", "\u62c9\u59c6",
        ]):
            return "donation"
        # 燒糊彈窗關鍵字
        if any(kw in text for kw in ["燒糊", "處理掉", "燒"]):
            return "spoiled"
        # 捐菜彈窗關鍵字
        if any(kw in text for kw in ["捐", "流浪", "拉姆"]):
            return "donation"
        return None

    def _has_popup_panel_fast(self):
        if not self.hwnd:
            return False
        try:
            img, w, h = capture_window(self.hwnd)
            img = img.convert("RGB")
            center_light = self._region_light_ratio(
                img, w, h, (300, 205, 660, 430),
                lambda r, g, b: r >= 225 and g >= 205 and b >= 145,
            )
            button_orange = self._region_light_ratio(
                img, w, h, (335, 385, 620, 445),
                lambda r, g, b: r >= 190 and 70 <= g <= 170 and b <= 80 and r > g + 30,
            )
            return center_light >= 0.28 and button_orange >= 0.025
        except Exception:
            return False

    # ── 快照與除錯 ─────────────────────────────────────────────────────────

    def _image_diff_score(self, before, after):
        if before is None or after is None or before.size != after.size:
            return 999.0
        diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
        stat = ImageStat.Stat(diff)
        return sum(stat.mean) / 3.0

    def _popup_region_changed(self, before, threshold=8.0):
        after = self._capture_popup_region()
        return self._image_diff_score(before, after) >= threshold

    def _detect_popup_type_retry(self, attempts=3, delay=0.2):
        for _ in range(max(1, attempts)):
            popup_type = self._detect_popup_type()
            if popup_type:
                return popup_type
            if self._stop.is_set():
                return None
            time.sleep(delay)
        return None

    def _handle_popup_guard(self, log, allow_unknown=False):
        if not self._has_popup_panel_fast():
            return None
        popup_type = self._detect_popup_type_retry(attempts=2, delay=0.15)
        confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        cancel_btn = self.recipe.get("cancel_btn", DEFAULT_RECIPE["cancel_btn"])

        if popup_type == "spoiled":
            log("彈窗守門員：偵測到腐壞，按確認清除")
            self.click_real(*confirm_btn, delay=0.8)
            return "spoiled"

        if popup_type == "donation":
            log("彈窗守門員：偵測到捐菜，按取消")
            self.click_real(*cancel_btn, delay=0.5)
            return "donation"

        if not allow_unknown:
            return None

        before = self._capture_popup_region()
        if before is None:
            return None
        log("彈窗守門員：彈窗文字看不清，先按取消")
        self.click_real(*cancel_btn, delay=0.5)
        if self._popup_region_changed(before):
            return "unknown_cancel"

        log("彈窗守門員：取消無效，改按確認")
        self.click_real(*confirm_btn, delay=0.8)
        return "unknown_confirm"

    def _region_light_ratio(self, img, w, h, box, predicate):
        scale = max(w / MOLE_W, h / MOLE_H)
        x1, y1, x2, y2 = box
        left = max(0, int(x1 * scale))
        top = max(0, int(y1 * scale))
        right = min(w, int(x2 * scale))
        bottom = min(h, int(y2 * scale))
        if right <= left or bottom <= top:
            return 0.0
        region = img.crop((left, top, right, bottom))
        total = max(1, region.size[0] * region.size[1])
        hits = 0
        for r, g, b in region.getdata():
            if predicate(r, g, b):
                hits += 1
        return hits / total

    def _detect_known_notice_popup(self):
        if not self.hwnd:
            return None
        try:
            img, w, h = capture_window(self.hwnd)
            img = img.convert("RGB")

            center_white = self._region_light_ratio(
                img, w, h, (360, 245, 600, 365),
                lambda r, g, b: r >= 235 and g >= 225 and b >= 185,
            )
            star_left = self._region_light_ratio(
                img, w, h, (290, 225, 475, 425),
                lambda r, g, b: r >= 235 and g >= 225 and b >= 175,
            )
            star_right = self._region_light_ratio(
                img, w, h, (495, 210, 685, 440),
                lambda r, g, b: r >= 235 and g >= 225 and b >= 175,
            )

            text = ""
            if center_white >= 0.45 or (star_left >= 0.35 and star_right >= 0.35):
                text = self._ocr_screen_region(300, 180, 700, 490)

            if text:
                if any(kw in text for kw in [
                    "\u7d2f\u8a08", "\u7d2f\u8ba1", "\u5728\u7dda", "\u5728\u7ebf",
                    "\u5c0f\u6642", "\u5c0f\u65f6",
                ]):
                    return "time"
                if any(kw in text for kw in [
                    "\u606d\u559c", "\u5eda\u85dd", "\u53a8\u827a",
                    "\u63d0\u9ad8", "\u734e\u52f5", "\u5956\u52b1",
                ]):
                    return "star"
                if "\u77e5\u9053" in text:
                    if star_left >= 0.35 and star_right >= 0.35:
                        return "star"
                    if center_white >= 0.45:
                        return "time"

            if center_white >= 0.62:
                return "time"
            if star_left >= 0.45 and star_right >= 0.45:
                return "star"
        except Exception:
            return None
        return None

    def _handle_known_notice_popup(self, log=None):
        notice = self._detect_known_notice_popup()
        if not notice:
            return False
        if notice == "star":
            buttons = [(480, 468), (480, 462)]
            msg = "\u5075\u6e2c\u5230\u505a\u83dc\u5347\u661f\u901a\u77e5\uff0c\u95dc\u9589"
        else:
            pt = tuple(self.settings.get("btn_online_time_ok", [480, 410]))
            buttons = [pt, (pt[0], pt[1] + 5), (pt[0], pt[1] - 5)]
            msg = "\u5075\u6e2c\u5230\u6642\u9593\u901a\u77e5\uff0c\u95dc\u9589"
        if log:
            log(msg)
        for i, btn in enumerate(buttons):
            self.click_real(*btn, delay=0.25)
            if i == len(buttons) - 1 or not self._detect_known_notice_popup():
                break
        return True

    def _clear_blocking_overlays(self, log=None, close_recipe=False, attempts=3):
        handled = False

        def _log(msg):
            if log:
                log(msg)

        for _ in range(max(1, attempts)):
            if self._stop.is_set():
                break

            if self._handle_known_notice_popup(log):
                handled = True
                continue

            if self._close_happy_spin_popup(log):
                handled = True
                continue

            popup_result = self._handle_popup_guard(_log, allow_unknown=False)
            if popup_result:
                handled = True
                continue

            if close_recipe and self._is_recipe_open_fast():
                _log("\u5075\u6e2c\u5230\u98df\u8b5c\u906e\u64cb\uff0c\u5148\u95dc\u9589")
                self.click_real(*self.recipe["close"], delay=0.35)
                handled = True
                continue

            break

        return handled

    def _progress_bar_score(self, sx, sy):
        if not self.hwnd:
            return 0.0
        try:
            img, w, h = capture_window(self.hwnd)
            img = img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
            box = self.settings.get("progress_bar_box", [-85, -85, 85, -45])
            left = max(0, int((sx + box[0]) * scale))
            top = max(0, int((sy + box[1]) * scale))
            right = min(w, int((sx + box[2]) * scale))
            bottom = min(h, int((sy + box[3]) * scale))
            if right <= left or bottom <= top:
                return 0.0
            region = img.crop((left, top, right, bottom))
            pixels = region.getdata()
            total = max(1, region.size[0] * region.size[1])
            hits = 0
            for r, g, b in pixels:
                if r >= 185 and g >= 105 and b <= 110 and r > g + 25:
                    hits += 1
            return hits / total
        except Exception:
            return 0.0

    def _is_progress_bar_visible(self, sx, sy):
        threshold = self.settings.get("progress_bar_pct_threshold", 0.025)
        return self._progress_bar_score(sx, sy) >= threshold

    def _recipe_panel_score(self):
        if not self.hwnd:
            return 0.0
        try:
            img, w, h = capture_window(self.hwnd)
            img = img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
            # 食譜面板中央到下方有大量穩定橘黃色 UI，餐廳主畫面同區域不會整片命中。
            left = max(0, int(300 * scale))
            top = max(0, int(120 * scale))
            right = min(w, int(865 * scale))
            bottom = min(h, int(500 * scale))
            region = img.crop((left, top, right, bottom))
            total = max(1, region.size[0] * region.size[1])
            hits = 0
            for r, g, b in region.getdata():
                if r >= 190 and 95 <= g <= 215 and b <= 95 and r > g + 20:
                    hits += 1
            return hits / total
        except Exception:
            return 0.0

    def _is_recipe_open_fast(self):
        return self._recipe_panel_score() >= 0.12

    def _wait_recipe_closed(self, timeout=2.5):
        deadline = time.time() + timeout
        misses = 0
        while time.time() < deadline and not self._stop.is_set():
            if self._is_recipe_open_fast():
                misses = 0
            else:
                misses += 1
                if misses >= 3:
                    return True
            time.sleep(0.12)
        return False

    def _wait_recipe_closed_and_first_progress(self, sx, sy, timeout=2.0):
        deadline = time.time() + timeout
        misses = 0
        first_bar_seen = False
        bar_threshold = self.settings.get("progress_bar_pct_threshold", 0.025)
        while time.time() < deadline and not self._stop.is_set():
            try:
                img, w, h = capture_window(self.hwnd)
                img = img.convert("RGB")
                scale = max(w / MOLE_W, h / MOLE_H)

                box = self.settings.get("progress_bar_box", [-85, -85, 85, -45])
                left = max(0, int((sx + box[0]) * scale))
                top = max(0, int((sy + box[1]) * scale))
                right = min(w, int((sx + box[2]) * scale))
                bottom = min(h, int((sy + box[3]) * scale))
                if right > left and bottom > top:
                    region = img.crop((left, top, right, bottom))
                    total = max(1, region.size[0] * region.size[1])
                    hits = 0
                    for r, g, b in region.getdata():
                        if r >= 185 and g >= 105 and b <= 110 and r > g + 25:
                            hits += 1
                    if hits / total >= bar_threshold:
                        first_bar_seen = True

                left = max(0, int(300 * scale))
                top = max(0, int(120 * scale))
                right = min(w, int(865 * scale))
                bottom = min(h, int(500 * scale))
                recipe_open = False
                if right > left and bottom > top:
                    region = img.crop((left, top, right, bottom))
                    total = max(1, region.size[0] * region.size[1])
                    hits = 0
                    for r, g, b in region.getdata():
                        if r >= 190 and 95 <= g <= 215 and b <= 95 and r > g + 20:
                            hits += 1
                    recipe_open = hits / total >= 0.12
            except Exception:
                recipe_open = self._is_recipe_open_fast()

            if recipe_open:
                misses = 0
            else:
                misses += 1
                if misses >= 2:
                    return True, first_bar_seen
            time.sleep(0.05)
        return False, first_bar_seen

    def _game_scene_score(self):
        if not self.hwnd:
            return 0.0
        try:
            img, w, h = capture_window(self.hwnd)
            img = img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
            boxes = [
                (520, 500, 960, 560),  # bottom action bar
                (650,  40, 960, 170),  # top-right shortcuts
                (  0, 500, 360, 560),  # bottom-left chat/status bar
            ]
            scores = []
            for x1, y1, x2, y2 in boxes:
                left = max(0, int(x1 * scale))
                top = max(0, int(y1 * scale))
                right = min(w, int(x2 * scale))
                bottom = min(h, int(y2 * scale))
                if right <= left or bottom <= top:
                    continue
                region = img.crop((left, top, right, bottom))
                total = max(1, region.size[0] * region.size[1])
                hits = 0
                for r, g, b in region.getdata():
                    if (
                        (r >= 170 and 60 <= g <= 230 and b <= 150 and r > b + 35) or
                        (r >= 230 and g >= 220 and b >= 185)
                    ):
                        hits += 1
                scores.append(hits / total)
            if not scores:
                return 0.0
            bottom_bar_ok = scores[0] >= 0.025
            other_ui_ok = any(score >= 0.025 for score in scores[1:])
            return 1.0 if bottom_bar_ok and other_ui_ok else 0.0
        except Exception:
            return 0.0

    def _is_game_scene_loaded_fast(self):
        return self._game_scene_score() >= 0.50

    def _has_game_action_bar_text(self):
        text = self._ocr_screen_region(520, 495, 950, 560)
        return any(kw in text for kw in [
            "\u52d5\u4f5c", "\u5c0e\u822a", "\u80cc\u5305", "\u597d\u53cb", "\u5bb6\u5712", "\u5730\u76e4", "\u5546\u57ce"
        ])

    def _is_game_scene_loaded(self, require_text=False):
        if self._is_game_scene_loaded_fast() and not require_text:
            return True
        if self._is_game_scene_loaded_fast() and self._has_game_action_bar_text():
            return True
        return self._has_game_action_bar_text()

    def _wait_for_game_scene(self, timeout=12.0, on_status=None, require_text=False):
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop.is_set():
            if self._is_game_scene_loaded(require_text=require_text):
                return True
            if on_status:
                on_status("等待進入遊戲場景…")
            if not self.wait(0.45):
                return False
        return False

    def _wait_for_progress_bar(self, sx, sy, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline and not self._stop.is_set():
            if self._is_progress_bar_visible(sx, sy):
                return True
            time.sleep(0.04)
        return False

    def _wait_for_progress_bar_gone(self, sx, sy, max_wait=None):
        if max_wait is None:
            max_wait = float(self.settings.get("progress_bar_max_wait", 5.0))
        deadline = time.time() + max_wait
        misses = 0
        required_misses = max(1, int(self.settings.get("progress_gone_misses", 2)))
        while time.time() < deadline and not self._stop.is_set():
            if self._is_progress_bar_visible(sx, sy):
                misses = 0
            else:
                misses += 1
                if misses >= required_misses:
                    return True
            time.sleep(0.06)
        return not self._stop.is_set()

    def save_live_snapshot(self, label=""):
        """
        把目前遊戲畫面 + 所有鍋爐的偵測結果存到桌面 bot_live.png，
        讓外部工具（Claude）即時讀取，不需 Debug 模式也能呼叫。
        標記內容：
          - 鍋爐位置（白圈），旁邊顯示偵測到的狀態
          - 各偵測點位置：黃=done, 橙=clock, 紅=spoiled
          - 每個偵測點顯示最小 Δ 值
        """
        if not self.hwnd:
            return
        try:
            from PIL import ImageDraw
            raw_img, w, h = capture_window(self.hwnd)
            img   = raw_img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
            draw  = ImageDraw.Draw(img)

            def px(mx, my):
                return int(mx * scale), int(my * scale)

            # 標題列
            ts = time.strftime("%H:%M:%S")
            draw.rectangle([0, 0, img.width, 26], fill=(0, 0, 0))
            draw.text((4, 5), f"{ts}  {label}", fill="white")

            threshold = self.settings.get("state_threshold", 40)
            state_fill = {"cooking": (255,140,0), "done": (255,220,0),
                          "spoiled": (220,50,50), "unknown": (160,160,160)}

            for i, (sx2, sy2) in enumerate(self.stoves):
                state = self.detect_stove_state(sx2, sy2)
                col   = state_fill.get(state, (160,160,160))
                spx, spy = px(sx2, sy2)
                r = 13
                draw.ellipse([spx-r, spy-r, spx+r, spy+r], outline=col, width=3)
                draw.text((spx-6, spy-8),  str(i+1), fill=col)
                draw.text((spx-r, spy+r+2), state[:4], fill=col)

                # 畫出各偵測點及 Δ 值
                checks = [
                    ("done_points",    "done_color",    "done_offset",    "yellow", 4),
                    ("clock_points",   "clock_color",   "clock_offset",   "orange", 4),
                    ("spoiled_points", "spoiled_color", "spoiled_offset", "red",    6),
                ]
                for pts_key, col_key, off_key, dot_col, spread in checks:
                    pts   = self.settings.get(pts_key) or []
                    color = self.settings.get(col_key)
                    off   = self.settings.get(off_key) or [0, 0]
                    if pts:
                        # 個別校準模式：只顯示該鍋爐自己的點
                        if len(pts) == len(self.stoves):
                            try:
                                si = list(self.stoves).index((sx2, sy2))
                                e = pts[si]
                                entries = [(sx2+e[0], sy2+e[1], (e[2],e[3],e[4]))]
                            except (ValueError, IndexError):
                                entries = [(sx2+e[0], sy2+e[1], (e[2],e[3],e[4])) for e in pts]
                        else:
                            entries = [(sx2+e[0], sy2+e[1], (e[2],e[3],e[4])) for e in pts]
                    elif color:
                        entries = [(sx2+off[0], sy2+off[1], tuple(color))]
                    else:
                        continue
                    for (mx, my, ref) in entries:
                        best = 999
                        for ddx, ddy in ((0,0),(spread,0),(-spread,0),(0,spread),(0,-spread)):
                            d = sum(abs(a-b) for a,b in zip(img.getpixel(
                                (min(max(int((mx+ddx)*scale),0),w-1),
                                 min(max(int((my+ddy)*scale),0),h-1))), ref))
                            if d < best:
                                best = d
                        dpx, dpy = px(mx, my)
                        mark = "✓" if best < threshold else f"Δ{best}"
                        draw.ellipse([dpx-5, dpy-5, dpx+5, dpy+5], outline=dot_col, width=2)
                        draw.text((dpx+7, dpy-7), mark, fill=dot_col)

            os.makedirs(os.path.dirname(LIVE_SNAP), exist_ok=True)
            img.save(LIVE_SNAP)
        except Exception as e:
            pass

    def detect_stove_state(self, sx, sy):
        """
        比對鍋爐狀態，回傳 "done" / "cooking" / "unknown"。
        腐壞不在此處偵測，改由 _open_recipe_and_cook 點擊後判斷彈窗類型處理。

        done：時鐘填滿（白色扇形消失）或 done_hsv_list / done_points 命中
        cooking：時鐘邊框命中且內部仍有白色扇形
        unknown：以上皆不符合（空鍋爐 / 腐壞 / 偵測失敗）
        """
        threshold = self.settings.get("state_threshold", 40)

        try:
            raw_img, w, h = capture_window(self.hwnd)
            img   = raw_img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
        except Exception:
            return "unknown"

        def get_px(mx, my):
            px = min(max(int(mx * scale), 0), w - 1)
            py = min(max(int(my * scale), 0), h - 1)
            return img.getpixel((px, py))

        def best_match(mx, my, ref_color, spread=4):
            best = 999
            for ddx, ddy in ((0, 0), (spread, 0), (-spread, 0), (0, spread), (0, -spread)):
                d = self.color_diff(get_px(mx + ddx, my + ddy), ref_color)
                if d < best:
                    best = d
            return best

        def check_hsv_state(hsv_list_key):
            """
            若設定了 HSV 清單，取本鍋爐對應的 HSV config 偵測。
            回傳 (hit: bool, score: int, xy: tuple) 或 None（未設定）。
            score = int((1 - pct) * 100)，越小越好，和 RGB Δ 相同方向。
            """
            hsv_list = self.settings.get(hsv_list_key) or []
            if not hsv_list:
                return None
            try:
                idx = list(self.stoves).index((sx, sy))
                cfg = hsv_list[idx] if idx < len(hsv_list) else None
            except (ValueError, IndexError):
                cfg = None
            if not cfg:
                return None
            cx = sx + cfg.get("cx", 0)
            cy = sy + cfg.get("cy", 0)
            radius        = cfg.get("radius", 10)
            h_range       = cfg.get("h", [0, 360])
            s_range       = cfg.get("s", [0, 100])
            v_range       = cfg.get("v", [0, 100])
            pct_threshold = cfg.get("pct", 0.12)

            # ── 時鐘校準品質護欄 ───────────────────────────────
            # H 跨度 >= 300°（幾乎任何顏色都算命中）→ 偵測完全不可靠，
            # 視為未校準，避免空鍋爐被誤判為「烹飪中」。
            if hsv_list_key == "clock_hsv_list":
                h_span = (h_range[1] - h_range[0]) if h_range[1] > h_range[0] else \
                         (360 - h_range[0] + h_range[1])
                if h_span >= 300:
                    return None   # 校準過寬，跳過，fallback 到動態畫素偵測

            pct   = _hsv_match_pct(img, scale, cx, cy, radius, h_range, s_range, v_range)
            score = int((1.0 - pct) * 100)
            return pct >= pct_threshold, score, (cx, cy), pct

        def check_state(points_key, old_color_key, old_offset_key, spread=4):
            """
            先檢查多點清單，再 fallback 舊格式。
            回傳 (偵測到: bool, 最佳 Δ: int, 第一個點的 mole 座標 for debug)

            「個別校準模式」：若 points 的數量 == 鍋爐數，每個鍋爐只取對應位置的點，
            避免其他鍋爐的偵測點互相干擾。
            「共用模式」：points 數量 < 鍋爐數，所有鍋爐共用同一批點（舊行為）。
            """
            points = self.settings.get(points_key) or []
            if points:
                # 個別校準模式：找出這個鍋爐對應的點
                if len(points) == len(self.stoves):
                    try:
                        idx = list(self.stoves).index((sx, sy))
                        relevant = [points[idx]]
                    except ValueError:
                        relevant = points   # 找不到就退回共用
                else:
                    relevant = points       # 共用模式

                best_overall = 999
                first_xy = (sx + relevant[0][0], sy + relevant[0][1])
                for entry in relevant:
                    dx, dy, r, g, b = entry
                    d = best_match(sx + dx, sy + dy, (r, g, b), spread)
                    if d < best_overall:
                        best_overall = d
                    if d < threshold:
                        return True, d, first_xy
                return False, best_overall, first_xy
            # fallback 舊格式
            color = self.settings.get(old_color_key)
            off   = self.settings.get(old_offset_key) or [0, 0]
            if not color:
                return False, 999, (sx, sy)
            mx, my = sx + off[0], sy + off[1]
            d = best_match(mx, my, tuple(color), spread)
            return d < threshold, d, (mx, my)

        markers = [(sx, sy, "white", "stove")]

        # 腐壞偵測已移至點擊後彈窗偵測處理，detect_stove_state 只偵測 done / cooking。

        _hsv_d = check_hsv_state("done_hsv_list")
        if _hsv_d is not None:
            hit_d, diff_d, (dx, dy), _ = _hsv_d
            markers.append((dx, dy, "yellow", f"done {int((1-diff_d/100)*100)}%"))
        else:
            hit_d, diff_d, (dx, dy) = check_state("done_points", "done_color", "done_offset")
            markers.append((dx, dy, "yellow", f"done Δ{diff_d}"))

        # 時鐘偵測（橙色邊框 → 確認時鐘存在）
        clock_calibrated = bool(
            self.settings.get("clock_hsv_list") or
            self.settings.get("clock_points") or self.settings.get("clock_color")
        )
        clock_hit, clock_diff, clock_pt, clock_raw_pct = False, 999, (sx, sy), 0.0
        if clock_calibrated:
            _hsv_ck = check_hsv_state("clock_hsv_list")
            if _hsv_ck is not None:
                clock_hit, clock_diff, clock_pt, clock_raw_pct = _hsv_ck
                markers.append((*clock_pt, "orange", f"ck {clock_raw_pct*100:.0f}%"))
            else:
                # RGB 時鐘需時序重試（動畫）
                for _sample in range(3):
                    if _sample > 0:
                        time.sleep(0.15)
                        try:
                            raw_img, w, h = capture_window(self.hwnd)
                            img   = raw_img.convert("RGB")
                            scale = max(w / MOLE_W, h / MOLE_H)
                        except Exception:
                            break
                    h_t, d_t, p_t = check_state("clock_points", "clock_color", "clock_offset")
                    if d_t < clock_diff:
                        clock_diff, clock_pt = d_t, p_t
                    if h_t:
                        clock_hit = True
                        break
                markers.append((*clock_pt, "orange", f"clock Δ{clock_diff}"))

        # 時鐘內部白色掃描：區分「烹飪中（有白色扇形）」vs「菜做好（全粉紅）」
        # 只在時鐘邊框偵測到的情況下執行
        full_clock_hit = False
        if clock_hit:
            interior_offsets = self.settings.get("clock_interior_offsets") or []
            try:
                _sidx = list(self.stoves).index((sx, sy))
            except ValueError:
                _sidx = -1
            if interior_offsets and 0 <= _sidx < len(interior_offsets) and interior_offsets[_sidx]:
                ioff = interior_offsets[_sidx]
                icx, icy = sx + ioff[0], sy + ioff[1]
                # 掃白色像素（V > 80%, S < 20%）
                white_pct = _hsv_match_pct(img, scale, icx, icy,
                                           radius=10,
                                           h_range=[0, 360],
                                           s_range=[0, 20],
                                           v_range=[80, 100])
                cook_thr = self.settings.get("cooking_white_threshold", 0.10)
                done_thr = self.settings.get("done_white_threshold",    0.05)
                markers.append((icx, icy, "white", f"wh {white_pct*100:.0f}%"))
                if white_pct <= done_thr:
                    # 白色很少 → 時鐘整個填滿粉紅 → 菜做好
                    full_clock_hit = True
                    clock_hit = False
                elif white_pct >= cook_thr:
                    pass   # 有白色扇形 → 確認烹飪中，保持 clock_hit=True
                # 模糊區間：保持 clock_hit=True（寧可誤判為烹飪，等下一輪再確認）

        # 建立候選集：只有 done / cooking，腐壞改由點擊後彈窗偵測
        candidates = {}
        if hit_d:          candidates["done"]    = diff_d
        if full_clock_hit: candidates["done"]    = min(candidates.get("done", 999), clock_diff)
        if clock_hit:      candidates["cooking"] = clock_diff

        if not candidates:
            return "unknown"

        # done 優先於 cooking（食物做完後時鐘也是橙色，兩者同時命中時取 done）
        if "done" in candidates and "cooking" in candidates:
            del candidates["cooking"]

        best = min(candidates, key=candidates.get)
        if best == "done":
            self._debug_capture(f"done_{sx}_{sy}", markers)
        return best

    def _detect_safe(self, sx, sy):
        """
        嚴謹版狀態偵測：連偵測兩次（間隔 0.3 秒），採保守判斷。
        任一次偵測到 cooking 即回傳，兩次任一 done 才算 done。
        腐壞已移至點擊後彈窗偵測，不在此處判斷。
        """
        s1 = self.detect_stove_state(sx, sy)
        if s1 == "cooking":
            return "cooking"
        time.sleep(0.3)
        s2 = self.detect_stove_state(sx, sy)
        if s2 == "cooking":
            return "cooking"
        if s1 == "done" or s2 == "done":
            return "done"
        return "unknown"

    def _is_in_restaurant(self):
        """
        確認目前是否在餐廳畫面。
        若尚未校準確認點，預設視為在餐廳（不阻擋流程）。
        """
        pt    = self.settings.get("restaurant_pt")
        color = self.settings.get("restaurant_color")
        if not pt or not color:
            return True
        threshold = self.settings.get("state_threshold", 40)
        current = self.get_pixel(*pt)
        if self.color_diff(current, tuple(color)) < threshold:
            return True
        if self._is_recipe_open_fast():
            return True
        return bool(self._detect_known_notice_popup())

    def is_recipe_open(self):
        """OCR 偵測畫面上是否出現「食譜」標題文字。
        不再用單點像素差異判斷，避免畫面變化時誤判食譜開啟並點到右上活動按鈕。"""
        if not self.hwnd:
            return False
        if self._is_recipe_open_fast():
            return True
        try:
            img, w, h = capture_window(self.hwnd)
            img   = img.convert("RGB")
            scale = max(w / MOLE_W, h / MOLE_H)
            cx, cy = self.recipe["check_pt"]
            # 截取 check_pt 左側延伸區域，涵蓋「食譜」標題文字位置
            left  = max(0, int((cx - 250) * scale))
            right = min(w, int((cx + 150) * scale))
            top   = max(0, int((cy -  40) * scale))
            bot   = min(h, int((cy +  30) * scale))
            region = img.crop((left, top, right, bot))
            text = self._ocr_image(region)
            if text:
                return "食譜" in text
        except Exception:
            pass
        return False

    # ── 鍋爐動作：收菜 / 做菜步驟 ────────────────────────

    def _collect_food(self, sx, sy, log):
        """收菜（食物做好時點鍋爐）"""
        log("收菜…")
        self.click(sx, sy, delay=0.5)
        self.wait(1.5)

    def _do_steps_progress(self, sx, sy, log, first_step_seen=False):
        labels = ["製作餐具", "放食材", "開始烹飪"]

        for step, label in enumerate(labels):
            if self._stop.is_set():
                return
            self._handle_known_notice_popup(log)

            log(f"{label}...")
            bar_seen = False
            tries = 1 if first_step_seen and step == 0 else 2
            for click_try in range(tries):
                if first_step_seen and step == 0:
                    if self._is_progress_bar_visible(sx, sy):
                        bar_seen = True
                        break
                    bar_seen = True
                    break

                self.click(sx, sy, delay=0.04)
                timeout = float(self.settings.get("progress_start_timeout", 0.65))
                if self._wait_for_progress_bar(sx, sy, timeout=timeout):
                    bar_seen = True
                    break

                if self._handle_known_notice_popup(log):
                    return

                popup_result = self._handle_popup_guard(log, allow_unknown=True)
                if popup_result in ("donation", "unknown_cancel"):
                    log("彈窗已關閉，這爐跳過")
                    return
                if popup_result in ("spoiled", "unknown_confirm"):
                    log("腐壞已清除，這爐下輪重試")
                    return

                if click_try == 0:
                    log(f"{label}：沒看到讀條，補點一次")
                    time.sleep(0.12)

            if not bar_seen:
                log(f"{label}：兩次都沒看到讀條，跳過這爐")
                self._debug_capture(f"no_progress_{sx}_{sy}_step{step+1}")
                return

            log(f"{label}：讀條中")
            self._wait_for_progress_bar_gone(sx, sy)

            if step == 2:
                log("已進入烹飪倒數")
                return

            time.sleep(0.12)

    def _do_steps(self, sx, sy, log, first_step_seen=False):
        return self._do_steps_progress(sx, sy, log, first_step_seen=first_step_seen)
        """
        執行 3 個烹飪步驟（製作餐具、放食材、開始烹飪）。
        純靠讀條（像素變化）判斷每步是否完成，不做額外狀態偵測：
          有讀條 → 等結束 → 繼續下一步
          step 2 讀條結束 → 直接宣告烹飪開始
          無讀條 → 點取消關掉可能的彈窗，結束（讓下輪重試）
        """
        cancel_btn = self.recipe.get("cancel_btn", DEFAULT_RECIPE["cancel_btn"])
        labels = ["製作餐具", "放食材", "開始烹飪"]

        for step in range(3):
            if self._stop.is_set(): return

            log(f"{labels[step]}…")

            # 點一次，沒觸發讀條就再點一次，兩次都沒反應才放棄
            bar_ok, bar_color = False, None
            for click_try in range(2):
                pre = self.get_pixel(sx, sy)
                self.click(sx, sy, delay=0.2)
                ok, _, color = self.wait_for_pixel_change(
                    sx, sy, timeout=2.5, baseline=pre)
                if ok:
                    bar_ok, bar_color = True, color
                    break
                if click_try == 0:
                    log(f"{labels[step]}：沒觸發讀條，補點一次…")
                    time.sleep(0.3)

            if not bar_ok:
                log(f"{labels[step]}：兩次都無讀條，關彈窗等下輪")
                self._debug_capture(f"no_bar_{sx}_{sy}_step{step+1}")
                self.click_real(*cancel_btn, delay=0.5)
                return

            log(f"{labels[step]}：讀條中…")
            deadline = time.time() + 20.0
            while time.time() < deadline and not self._stop.is_set():
                if self.color_diff(self.get_pixel(sx, sy), bar_color) > 40:
                    break
                time.sleep(0.3)

            if step == 2:
                log("已進入烹飪 ✓")
                return

            time.sleep(0.5)  # 讓遊戲回到可點擊狀態再進下一步

    def _open_recipe_and_cook(self, sx, sy, page, dish, log):
        """
        點鍋爐開食譜 → 選菜 → 做步驟。

        流程：
          1. 點鍋爐，等食譜開啟（1.5 秒）
             → 開了 → 做菜
          2. 沒開 → 偵測像素動畫：
             → 烹飪中（像素在動）→ 取消捐菜彈窗，跳下一爐
          3. 鍋爐靜止 → OCR 判斷：
             → 燒糊彈窗 → 確認清除 → 等 harvest_wait 秒 → 再點一次 → 做菜或跳過
             → 捐菜彈窗（做菜中）→ 取消，跳下一爐
             → 無彈窗（可能剛收菜完）→ 等 harvest_wait 秒 → 再點一次 → 做菜或跳過
        """
        check        = self.recipe["check_pt"]
        confirm_btn  = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        cancel_btn   = self.recipe.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"])
        harvest_wait = self.settings.get("harvest_wait", 3)

        def _click_and_wait_recipe(timeout=None):
            """點一次鍋爐，等食譜開啟，回傳是否開啟"""
            if timeout is None:
                timeout = float(self.settings.get("recipe_open_timeout", 1.4))
            self.click(sx, sy, delay=0.12)
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self._stop.is_set():
                    return False
                if self._close_happy_spin_popup(log):
                    return False
                if self._handle_known_notice_popup(log):
                    continue
                if self._is_recipe_open_fast():
                    return True
                time.sleep(0.10)
            return self.is_recipe_open()

        def _do_cook():
            select_result = self._select_dish(sx, sy, page, dish, check, log)
            if select_result:
                self._do_steps(sx, sy, log, first_step_seen=(select_result == "first_bar"))

        # 食譜已開著（例如上輪未關），直接選菜
        if self._close_happy_spin_popup(log):
            return
        self._handle_known_notice_popup(log)
        if self.is_recipe_open():
            log("食譜已開著，直接選菜…")
            _do_cook()
            return

        # ── 第一次點鍋爐 ──
        if _click_and_wait_recipe():
            log("食譜已開啟 ✓")
            _do_cook()
            return

        # 食譜沒開──偵測像素動畫（烹飪中 or 靜止）
        popup_result = self._handle_popup_guard(log, allow_unknown=True)
        if popup_result in ("donation", "unknown_cancel"):
            return
        if popup_result in ("spoiled", "unknown_confirm"):
            log(f"等待 {harvest_wait} 秒後重試開食譜...")
            if not self.wait(min(0.5, harvest_wait)): return
            if _click_and_wait_recipe():
                log("清除後食譜開啟 ✓")
                _do_cook()
            else:
                log("清除後仍無法開食譜，跳過")
            return

        time.sleep(0.12)
        p1 = self.get_pixel(sx, sy)
        time.sleep(0.22)
        p2 = self.get_pixel(sx, sy)

        if self.color_diff(p1, p2) > 15:
            # 烹飪中（像素仍在動）→ 可能跳出捐菜彈窗，取消後跳下一爐
            log("偵測到烹飪動畫，關捐菜彈窗，跳下一爐")
            self.click_real(*cancel_btn, delay=0.5)
            return

        # 鍋爐靜止：OCR 判斷彈窗類型
        popup_type  = self._detect_popup_type()
        ocr_preview = self._last_ocr_text[:30] if self._last_ocr_text else "（空）"
        log(f"OCR 讀到：{ocr_preview}")

        if popup_type == "spoiled":
            log("OCR：燒糊彈窗，按確認清除")
            self.click_real(*confirm_btn, delay=0.5)
            log(f"等待 {harvest_wait} 秒清除動畫…")
            if not self.wait(min(0.5, harvest_wait)): return
            if _click_and_wait_recipe():
                log("清除後食譜開啟 ✓")
                _do_cook()
            else:
                log("清除後仍無法開食譜，跳過")

        elif popup_type == "donation":
            log("OCR：捐菜彈窗（做菜中），按取消，跳下一爐")
            self.click_real(*cancel_btn, delay=0.5)

        else:
            # 無彈窗：可能剛收菜完，鍋爐需要稍等才能再開食譜
            log(f"無彈窗，等待 {harvest_wait} 秒後重新點鍋爐…")
            if not self.wait(min(0.5, harvest_wait)): return
            if _click_and_wait_recipe():
                log("收菜後食譜開啟 ✓")
                _do_cook()
            else:
                log("等待後仍無法開食譜，跳下一爐")

    def setup_stove(self, sx, sy, page, dish, on_status=None):
        """
        處理單個鍋爐。
        不做預先偵測，直接點鍋爐，由 _open_recipe_and_cook 根據點擊後的反應判斷：
          - 食譜開了 → 做菜
          - 偵測到烹飪中（點後仍在動）→ 捐菜彈窗 → 取消
          - 其他 → 腐壞彈窗或食物剛收走 → 確認後重試
        """
        def log(msg):
            if on_status: on_status(msg)

        self._open_recipe_and_cook(sx, sy, page, dish, log)

    def find_window(self):
        found = []
        def cb(hwnd, _):
            if "Adobe Flash Player" in win32gui.GetWindowText(hwnd) and win32gui.IsWindowVisible(hwnd):
                found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    def _is_window_alive(self):
        """確認 Flash Player 視窗仍然存在且可見"""
        if not self.hwnd:
            return False
        try:
            return (win32gui.IsWindow(self.hwnd) and
                    win32gui.IsWindowVisible(self.hwnd) and
                    "Adobe Flash Player" in win32gui.GetWindowText(self.hwnd))
        except Exception:
            return False

    def get_pixel(self, mole_x, mole_y):
        """取得摩爾座標的像素顏色 (R, G, B)"""
        try:
            img, w, h = capture_window(self.hwnd)
            scale = max(w / MOLE_W, h / MOLE_H)
            px = min(int(mole_x * scale), w - 1)
            py = min(int(mole_y * scale), h - 1)
            return img.convert("RGB").getpixel((px, py))
        except Exception:
            return (0, 0, 0)

    def color_diff(self, c1, c2):
        return sum(abs(a - b) for a, b in zip(c1, c2))

    def wait_for_pixel_change(self, mole_x, mole_y, timeout=5.0, threshold=40, baseline=None):
        """等到指定點顏色發生明顯變化，回傳 (成功, 基準色, 最終色)
        baseline 可在點擊前先傳入，避免 click delay 導致截到錯誤的基準色"""
        if baseline is None:
            baseline = self.get_pixel(mole_x, mole_y)
        deadline = time.time() + timeout
        current = baseline
        while time.time() < deadline:
            if self._stop.is_set():
                return False, baseline, current
            time.sleep(0.15)
            current = self.get_pixel(mole_x, mole_y)
            if self.color_diff(current, baseline) > threshold:
                return True, baseline, current
        return False, baseline, current

    def click(self, mole_x, mole_y, delay=0.1):
        """背景點擊（SendMessage），適合底層遊戲元素如鍋爐"""
        if not self.hwnd:
            return
        rect  = win32gui.GetClientRect(self.hwnd)
        w, h  = rect[2], rect[3]
        scale = max(w / MOLE_W, h / MOLE_H)
        cx, cy = int(mole_x * scale), int(mole_y * scale)
        lp = (cy << 16) | (cx & 0xFFFF)
        win32api.SendMessage(self.hwnd, 0x201, 0, lp)
        win32api.SendMessage(self.hwnd, 0x202, 0, lp)
        if delay > 0:
            self.wait(delay)

    def click_real(self, mole_x, mole_y, delay=0.1):
        """背景點擊（與 click 相同，保留名稱以相容舊呼叫）"""
        self.click(mole_x, mole_y, delay)

    def wait(self, seconds):
        for _ in range(int(seconds * 10)):
            if self._stop.is_set():
                return False
            time.sleep(0.1)
        return True

    def leave_and_return(self, on_status):
        door_out      = self.settings.get("door_out")
        door_waypoint = self.settings.get("door_waypoint")
        door_in       = self.settings.get("door_in")
        if door_out and door_in:
            on_status("防卡頓：出門…")
            self.click_real(*door_out, delay=2.5)
            if self._stop.is_set(): return
            if door_waypoint:
                on_status("防卡頓：走到入口…")
                self.click_real(*door_waypoint, delay=2.5)
                if self._stop.is_set(): return
            on_status("防卡頓：進門…")
            self.click_real(*door_in, delay=2.5)
            if self._stop.is_set(): return
            # 等畫面完全載入後再繼續，避免誤點右上角按鈕
            on_status("防卡頓：等待畫面載入…")
            self.wait(2.0)
            # 重新取食譜關閉基準色，進出後畫面已變，舊基準可能導致誤判
            if self.hwnd:
                self._recipe_closed_baseline = list(
                    self.get_pixel(*self.recipe["check_pt"])
                )
        else:
            btn_land = tuple(self.settings.get("btn_land", HOME_BTN))
            btn_restaurant = tuple(self.settings.get("btn_land_restaurant", RESTAURANT_BTN))
            on_status("防卡頓：開啟地盤…")
            self.click(*btn_land, delay=0.7)
            if self._stop.is_set(): return
            on_status("防卡頓：回到餐廳…")
            self.click(*btn_restaurant, delay=1.8)
        self._last_antlag = time.time()   # 記錄完成時間，供全局計時使用

    def wait_with_antlag(self, total_seconds, interval_seconds, on_status, msg):
        """
        等待 total_seconds 秒，期間每隔 interval_seconds 執行一次防卡頓。
        使用 _last_antlag 全局計時，掃描前若已做過防卡頓，等待期間不會重複太快觸發。
        """
        elapsed = 0.0
        while elapsed < total_seconds and not self._stop.is_set():
            rem = total_seconds - elapsed
            on_status(f"{msg}（剩餘 {int(rem//60)} 分 {int(rem%60)} 秒）")
            for _ in range(10):
                if self._stop.is_set():
                    return False
                time.sleep(0.1)
            if not self._is_window_alive():
                on_status("Flash Player 視窗已關閉，停止等待", error=True)
                return False
            elapsed += 1.0
            # 以 _last_antlag 判斷，和掃描前的防卡頓共用同一個計時器，不會重複觸發
            if (interval_seconds > 0 and elapsed < total_seconds and
                    time.time() - self._last_antlag >= interval_seconds):
                self.leave_and_return(on_status)
                self._clear_blocking_overlays(on_status, close_recipe=True)
                if not self._is_in_restaurant():
                    on_status("防卡頓後未偵測到餐廳，30 秒後重試…")
        return not self._stop.is_set()

    def navigate_to_page(self, target_page):
        r = self.recipe
        page_tabs = r.get("page_tabs", DEFAULT_RECIPE["page_tabs"])

        # 先連按左箭頭確保回到第 1 頁
        for _ in range(15):
            if self._stop.is_set(): return
            self.click_real(*r["left_arrow"], delay=0.15)
        time.sleep(0.2)

        if 1 <= target_page <= len(page_tabs):
            # 直接點 tab 按鈕，避免箭頭計數在遊戲卡頓時漏點
            self.click_real(*page_tabs[target_page - 1], delay=0.2)
        else:
            # 超出 tab 範圍（第 6 頁以上）：用右箭頭從第 1 頁導到目標頁
            for _ in range(target_page - 1):
                if self._stop.is_set(): return
                self.click_real(*r["right_arrow"], delay=0.2)

        time.sleep(0.5)  # 等頁面渲染完成（從 0.3 加長）

    def _select_dish(self, sx, sy, page, dish, check, log):
        """換頁 + 點菜色 + 等食譜關閉。成功回傳 True。"""
        log(f"切換到第 {page} 頁…")
        self.navigate_to_page(page)
        if self._stop.is_set(): return False
        self._handle_known_notice_popup(log)

        dishes = self.recipe.get("dishes", DEFAULT_RECIPE["dishes"])
        if not (1 <= dish <= len(dishes)):
            log(f"菜色位置 {dish} 超出範圍，請檢查設定")
            return False
        if not self.is_recipe_open():
            log("切頁後沒有確認到食譜開啟，停止本爐")
            return False

        dish_pt = dishes[dish - 1]
        log(f"點菜色 {dish}…")
        pre = self.get_pixel(*check)
        self.click_real(*dish_pt, delay=0.02)
        recipe_closed, first_bar_seen = self._wait_recipe_closed_and_first_progress(sx, sy, timeout=2.0)
        ok, _, _ = self.wait_for_pixel_change(*check, timeout=0.2, baseline=pre)
        if not recipe_closed:
            log("點菜後食譜仍開著，已關閉並停止本爐，避免誤點其他菜色")
            self.click_real(*self.recipe["close"], delay=0.5)
            return False
        if not ok:
            log("食譜已關閉，但偵測點變化不明顯，先更新基準")
        log("食譜已關閉 ✓")
        # 食譜剛關閉，順便更新基準色（最準確的時機）
        self._recipe_closed_baseline = list(self.get_pixel(*check))
        return "first_bar" if first_bar_seen else True

    # ── 斷線 / 閃退重連 ──────────────────────────────────

    def _ocr_screen_region(self, x1, y1, x2, y2):
        """截取遊戲畫面指定區域做 OCR，回傳文字。"""
        if not self.hwnd:
            return ""
        try:
            img, w, h = capture_window(self.hwnd)
            scale = max(w / MOLE_W, h / MOLE_H)
            region = img.convert("RGB").crop((
                max(0, int(x1 * scale)), max(0, int(y1 * scale)),
                min(w, int(x2 * scale)), min(h, int(y2 * scale)),
            ))
            return self._ocr_image(region)
        except Exception:
            return ""

    def _detect_disconnect_popup(self):
        """偵測斷線彈窗（本次連接已斷開）。
        先用像素快速判斷，再 OCR 確認，避免每輪都跑 OCR。"""
        r, g, b = self.get_pixel(480, 320)
        if not (r > 200 and g > 185):   # 彈窗背景是淺米色，平時不符合
            return False
        text = self._ocr_screen_region(200, 200, 760, 440)
        return "斷開" in text or "重新登" in text

    def _detect_happy_spin_popup(self):
        """偵測歡樂轉轉彈窗。
        只把大型彈窗文字算進來，避免右上角小活動圖示被誤認成彈窗。"""
        text = self._ocr_screen_region(220, 70, 780, 540)
        if not text:
            return False
        has_title = any(kw in text for kw in ["歡樂", "转转", "轉轉", "天天"])
        has_body = any(kw in text for kw in ["啟動", "启动", "剩餘", "剩余"])
        return has_title and has_body

    def _close_happy_spin_popup(self, on_status=None):
        if not self._detect_happy_spin_popup():
            return False
        btn = tuple(self.settings.get("btn_happy_spin_close", [705, 105]))
        if on_status:
            on_status("偵測到歡樂轉轉彈窗，關閉…")
        self.click(*btn, delay=0.8)
        return True

    def _wait_for_screen(self, keywords, region=(80, 40, 880, 520), timeout=20.0, on_status=None):
        """輪詢 OCR，等到畫面出現指定關鍵字之一，回傳 True/False。"""
        msg = "/".join(keywords)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop.is_set():
                return False
            text = self._ocr_screen_region(*region)
            if any(kw in text for kw in keywords):
                return True
            if on_status:
                on_status(f"等待畫面「{msg}」…")
            if not self.wait(0.7):
                return False
        return False

    def _handle_notice_popup(self, on_status):
        """處理系統提示 / 知道了彈窗（半夜維護公告等）。"""
        text = self._ocr_screen_region(180, 180, 780, 440)
        if any(kw in text for kw in ["系統提示", "知道了", "休息"]):
            btn = tuple(self.settings.get("btn_notice_ok", [480, 390]))
            on_status("偵測到系統提示，點知道了…")
            self.click(*btn, delay=1.0)

    def _navigate_to_restaurant(self, on_status):
        btn_land = tuple(self.settings.get("btn_land", HOME_BTN))
        btn_restaurant = tuple(self.settings.get("btn_land_restaurant", RESTAURANT_BTN))
        on_status("導航至餐廳：開啟地盤…")
        self.click(*btn_land, delay=0.7)
        if self._stop.is_set(): return False
        on_status("導航至餐廳：點選餐廳…")
        self.click(*btn_restaurant, delay=1.8)
        if self._stop.is_set(): return False

        if self.hwnd:
            self._recipe_closed_baseline = list(self.get_pixel(*self.recipe["check_pt"]))
        on_status("已導航至餐廳…")
        return True

    def _navigate_to_restaurant_after_login(self, on_status):
        if self._navigate_to_restaurant(on_status):
            on_status("登入完成，已導航至餐廳…")
            return True
        return False

    def _login_flow(self, on_status):
        """從主畫面完成整個登入流程直到進入遊戲。
        步驟：主畫面開始 → 角色登入 → 選伺服器快速開始 → 導航餐廳"""
        btn_start = tuple(self.settings.get("btn_game_start",  [484, 398]))
        btn_login = tuple(self.settings.get("btn_login",       [484, 432]))
        btn_quick = tuple(self.settings.get("btn_quick_start", [456, 517]))
        if self._close_happy_spin_popup(on_status):
            pass

        if self._wait_for_game_scene(timeout=0.8, on_status=None, require_text=True):
            return self._navigate_to_restaurant_after_login(on_status)

        if self._wait_for_screen(["摩爾莊園"], region=(80, 40, 880, 440), timeout=1.0, on_status=on_status):
            on_status("偵測到主畫面，點選「開始」…")
        else:
            on_status("未辨識到主畫面，嘗試點一次「開始」…")
        self.click(*btn_start, delay=0.7)
        if self._stop.is_set(): return False

        if self._wait_for_screen(["登入", "密碼"], timeout=1.5, on_status=on_status):
            on_status("偵測到登入畫面，點選「登入」…")
        else:
            on_status("未辨識到登入畫面，嘗試點一次「登入」…")
        self.click(*btn_login, delay=0.7)
        if self._stop.is_set(): return False

        if self._wait_for_screen(["選擇伺服器", "快速"], timeout=1.5, on_status=on_status):
            on_status("偵測到選伺服器畫面，點選「快速開始」…")
        else:
            on_status("未辨識到選伺服器畫面，嘗試點一次「快速開始」…")
        self.click(*btn_quick, delay=1.0)
        if self._stop.is_set(): return False

        on_status("等待進入遊戲場景…")
        if not self._wait_for_game_scene(timeout=8.0, on_status=on_status, require_text=False):
            on_status("\u9032\u5834\u5075\u6e2c\u672a\u78ba\u8a8d\uff0c\u6539\u7528\u4fdd\u5b88\u5c0e\u822a\u7e7c\u7e8c", error=False)

        self._handle_notice_popup(on_status)
        if not self.wait(1.0):
            return False
        return self._navigate_to_restaurant_after_login(on_status)

    def _launch_flash_and_login(self, on_status):
        """Flash 閃退：重啟 exe → 開啟遊戲 URL → 走登入流程。"""
        import subprocess
        exe  = (self.settings.get("flash_exe_path") or "").strip()
        url  = self.settings.get("game_url", "http://mole.61.com.tw/Client.swf")
        if not exe:
            on_status("請先設定 Flash Player 路徑", error=True)
            return False
        if not os.path.exists(exe):
            on_status(f"Flash Player 路徑不存在：{exe}", error=True)
            return False

        on_status("重啟 Flash Player…")
        try:
            subprocess.Popen([exe, url])
        except Exception as e:
            on_status(f"無法啟動 Flash Player：{e}", error=True)
            return False

        # 等視窗出現
        on_status("等待 Flash Player 視窗…")
        for _ in range(40):
            if self._stop.is_set(): return False
            if not self.wait(0.5):
                return False
            hwnd = self.find_window()
            if hwnd:
                self.hwnd = hwnd
                break
        else:
            on_status("Flash Player 視窗未出現，停止", error=True)
            return False
        if not self.wait(1.0):
            return False

        # 走登入流程
        return self._login_flow(on_status)

    def run(self, page, dish, scan_interval, antlag_minutes, on_status):
        self._stop.clear()
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗，嘗試自動開啟…")
            if not self._launch_flash_and_login(on_status):
                return

        try:
            antlag_sec = antlag_minutes * 60   # 0 = 完全關閉防卡頓

            # ── 啟動初始化 ──
            on_status("初始化中…")
            self._clear_blocking_overlays(on_status, close_recipe=True)

            # 1. 若食譜開著，先關掉再取基準色
            #    先用 check_pt 暖色判斷（食譜標題為橙金色），不靠基準色
            # 1. 若食譜開著（OCR 偵測「食譜」文字），先關掉
            if self.is_recipe_open():
                on_status("初始化：食譜開著，自動關閉…")
                self.click_real(*self.recipe["close"], delay=0.8)
                self.wait(0.8)
            # 取基準色（供 OCR 不可用時的像素 fallback）
            self._recipe_closed_baseline = list(self.get_pixel(*self.recipe["check_pt"]))

            # 2. 若不在餐廳，嘗試導航過去
            self._clear_blocking_overlays(on_status, close_recipe=True)
            if not self._is_in_restaurant():
                on_status("初始化：不在餐廳，嘗試導航…")
                if not self._navigate_to_restaurant(on_status):
                    return
                if self._stop.is_set(): return
                self.wait(2.0)
                self._clear_blocking_overlays(on_status, close_recipe=True)
                if not self._is_in_restaurant():
                    on_status("初始化：無法確認在餐廳，請手動前往後重啟", error=True)
                    return

            # 若未校準餐廳確認點，提醒但不阻擋
            if not self.settings.get("restaurant_pt") or not self.settings.get("restaurant_color"):
                on_status("提示：未校準餐廳確認點，建議校準以防止在餐廳外誤觸做菜")
                self.wait(2.0)

            on_status("初始化完成，開始掃描…")

            while not self._stop.is_set():
                # 每輪先確認視窗還在
                if not self._is_window_alive():
                    wait_sec = self.settings.get("restart_wait_seconds", 15)
                    on_status(f"Flash Player 視窗消失，等待 {wait_sec} 秒…")
                    deadline = time.time() + wait_sec
                    while time.time() < deadline and not self._stop.is_set():
                        if not self.wait(1.0):
                            break
                        if self._is_window_alive():
                            on_status("視窗已恢復，繼續掃描…")
                            break
                    else:
                        # 視窗沒回來，嘗試自動重啟
                        if not self._stop.is_set() and self.settings.get("flash_exe_path"):
                            if not self._launch_flash_and_login(on_status):
                                break
                        else:
                            on_status("Flash Player 視窗已關閉，停止機器人", error=True)
                            break
                    if self._stop.is_set(): break
                    continue

                # 偵測斷線彈窗（先快速像素判斷，有疑才 OCR）
                if self._detect_disconnect_popup():
                    on_status("偵測到斷線彈窗，執行重連…")
                    btn_confirm = tuple(self.settings.get("btn_disconnect_confirm", [478, 382]))
                    self.click(*btn_confirm, delay=1.5)
                    self.wait(2.0)
                    self._handle_notice_popup(on_status)
                    if not self._login_flow(on_status):
                        break
                    if self._stop.is_set(): break
                    continue

                # 掃描前防卡頓：若距上次防卡頓已超過設定間隔，先出去繞一圈再掃
                # 這樣即使掃描本身耗時，Flash Player 也不會在掃描前就已經積累太久
                self._clear_blocking_overlays(on_status, close_recipe=True)
                if antlag_sec > 0 and time.time() - self._last_antlag >= antlag_sec:
                    on_status("掃描前防卡頓…")
                    self.leave_and_return(on_status)
                    if self._stop.is_set(): break
                    self._clear_blocking_overlays(on_status, close_recipe=True)

                # 確認在餐廳內，否則嘗試導航回來
                self._clear_blocking_overlays(on_status, close_recipe=True)
                if not self._is_in_restaurant():
                    on_status("不在餐廳，嘗試返回…")
                    if not self._navigate_to_restaurant(on_status):
                        break
                    if self._stop.is_set(): break
                    self.wait(2.0)
                    self._clear_blocking_overlays(on_status, close_recipe=True)
                    if not self._is_in_restaurant():
                        on_status("無法確認在餐廳，跳過本輪掃描")
                        if not self.wait_with_antlag(scan_interval, antlag_sec, on_status, "等待重試"): break
                        continue

                # 只有偵測到食譜開著才按 X，避免誤點右上角按鈕
                if self.is_recipe_open():
                    self.click_real(*self.recipe["close"], delay=0.5)

                # 掃描所有鍋爐：已完成→收菜並重新做，烹飪中→跳過
                n = len(self.stoves)
                on_status(f"開始掃描（共 {n} 個鍋爐）…")
                if self._debug:
                    self.save_live_snapshot("掃描前")
                for i, (sx, sy) in enumerate(self.stoves):
                    self._clear_blocking_overlays(on_status, close_recipe=True)
                    if self._stop.is_set(): break
                    on_status(f"【鍋爐 {i+1}/{n}】掃描中…")
                    self.setup_stove(sx, sy, page, dish, on_status)
                    on_status(f"【鍋爐 {i+1}/{n}】完成")
                    if not self.wait(0.2): break

                if self._stop.is_set(): break

                # 等待下次掃描（含防卡頓）
                if not self.wait_with_antlag(scan_interval, antlag_sec, on_status, "等待掃描"): break
        finally:
            on_status("已停止")

    def stop(self):
        self._stop.set()


# ── 主介面 ────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("摩爾莊園｜餐廳自動做菜")
        self.root.resizable(False, False)

        self.stoves, self.recipe, settings = load_config()
        _extra_keys = ("restaurant_pt", "restaurant_color",
                       "door_out", "door_waypoint", "door_in",
                       "spoiled_color", "spoiled_offset",
                       "clock_color",   "clock_offset",
                       "done_color",    "done_offset",
                       "done_points", "clock_points", "spoiled_points",
                       "done_hsv_list", "clock_hsv_list", "spoiled_hsv_list",
                       "state_threshold",
                       "clock_interior_offsets",
                       "cooking_white_threshold", "done_white_threshold",
                       "recipe_open_timeout", "progress_start_timeout", "progress_gone_misses",
                       "smoke_offsets", "smoke_threshold", "smoke_pct_threshold",
                       "game_url",
                       "btn_disconnect_confirm", "btn_notice_ok", "btn_online_time_ok",
                       "btn_game_start", "btn_login", "btn_quick_start",
                       "btn_happy_spin_close",
                       "btn_land", "btn_land_restaurant")
        self._extra_settings = {k: settings[k] for k in _extra_keys}
        self.bot = RestaurantBot(self.stoves, self.recipe, settings)
        self._build_ui(settings)

    def _build_ui(self, settings):
        f = ttk.Frame(self.root, padding=12)
        f.pack(fill=tk.BOTH)

        self.vars = {}

        # ── 設定 ─────────────────────────────────────────
        grp_set = ttk.LabelFrame(f, text="設定", padding=(10, 4))
        grp_set.pack(fill=tk.X, pady=(0, 6))

        row1 = ttk.Frame(grp_set)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="食譜頁數 (1~10)", width=17, anchor=tk.W).pack(side=tk.LEFT)
        v_page = tk.IntVar(value=settings["page"])
        ttk.Spinbox(row1, from_=1, to=10, textvariable=v_page, width=5).pack(side=tk.LEFT)
        ttk.Label(row1, text="   菜的位置 (1~6)").pack(side=tk.LEFT)
        v_dish = tk.IntVar(value=settings["dish"])
        ttk.Spinbox(row1, from_=1, to=6, textvariable=v_dish, width=5).pack(side=tk.LEFT)
        self.vars["page"] = v_page
        self.vars["dish"] = v_dish

        row2 = ttk.Frame(grp_set)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="掃描間隔", width=17, anchor=tk.W).pack(side=tk.LEFT)
        v_min = tk.IntVar(value=settings.get("cook_minutes", 20))
        v_sec = tk.IntVar(value=settings.get("cook_seconds", 0))
        ttk.Spinbox(row2, from_=0, to=99, textvariable=v_min, width=4).pack(side=tk.LEFT)
        ttk.Label(row2, text=" 分 ").pack(side=tk.LEFT)
        ttk.Spinbox(row2, from_=0, to=59, textvariable=v_sec, width=4).pack(side=tk.LEFT)
        ttk.Label(row2, text=" 秒   防卡頓 ").pack(side=tk.LEFT)
        v_al = tk.IntVar(value=settings.get("antlag_minutes", 5))
        ttk.Spinbox(row2, from_=0, to=99, textvariable=v_al, width=4).pack(side=tk.LEFT)
        ttk.Label(row2, text=" 分（0=關）").pack(side=tk.LEFT)
        self.vars["cook_minutes"]  = v_min
        self.vars["cook_seconds"]  = v_sec
        self.vars["antlag_minutes"] = v_al

        row3 = ttk.Frame(grp_set)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="收菜等待", width=17, anchor=tk.W).pack(side=tk.LEFT)
        v_hw = tk.IntVar(value=settings.get("harvest_wait", 3))
        ttk.Spinbox(row3, from_=0, to=30, textvariable=v_hw, width=4).pack(side=tk.LEFT)
        ttk.Label(row3, text=" 秒（收菜後等待）   視窗等待 ").pack(side=tk.LEFT)
        v_rw = tk.IntVar(value=settings.get("restart_wait_seconds", 15))
        ttk.Spinbox(row3, from_=5, to=120, textvariable=v_rw, width=4).pack(side=tk.LEFT)
        ttk.Label(row3, text=" 秒（視窗消失後重試）").pack(side=tk.LEFT)
        self.vars["harvest_wait"] = v_hw
        self.vars["restart_wait_seconds"] = v_rw

        row4 = ttk.Frame(grp_set)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="Flash Player 路徑", width=17, anchor=tk.W).pack(side=tk.LEFT)
        v_exe = tk.StringVar(value=settings.get("flash_exe_path", ""))
        ttk.Entry(row4, textvariable=v_exe, width=42).pack(side=tk.LEFT)
        self.flash_browse_btn = ttk.Button(row4, text="瀏覽", command=self._browse_flash_exe)
        self.flash_browse_btn.pack(side=tk.LEFT, padx=(4, 0))
        self.vars["flash_exe_path"] = v_exe

        # ── 校準 ─────────────────────────────────────────
        grp_cal = ttk.LabelFrame(f, text="校準", padding=(10, 4))
        grp_cal.pack(fill=tk.X, pady=(0, 6))

        # 第一列：基礎設定校準
        row_c1 = ttk.Frame(grp_cal)
        row_c1.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row_c1, text="基礎：", width=5, foreground="gray").pack(side=tk.LEFT)
        self.calib_s    = ttk.Button(row_c1, text="鍋爐", command=self._calib_stoves)
        self.calib_r    = ttk.Button(row_c1, text="食譜", command=self._calib_recipe)
        self.calib_c    = ttk.Button(row_c1, text="彈窗", command=self._calib_cancel)
        self.calib_door = ttk.Button(row_c1, text="門口", command=self._calib_door)
        self.calib_rest = ttk.Button(row_c1, text="餐廳", command=self._calib_restaurant)
        self.calib_ocr  = ttk.Button(row_c1, text="測 OCR", command=self._test_ocr)
        for btn in (self.calib_s, self.calib_r, self.calib_c, self.calib_door, self.calib_rest, self.calib_ocr):
            btn.pack(side=tk.LEFT, padx=3)

        # 第二列：狀態偵測校準
        row_c2 = ttk.Frame(grp_cal)
        row_c2.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row_c2, text="偵測：", width=5, foreground="gray").pack(side=tk.LEFT)
        self.calib_sp     = ttk.Button(row_c2, text="狀態色", command=self._calib_state_colors)
        self.calib_clk_in = ttk.Button(row_c2, text="時鐘內部", command=self._calib_clock_interior)
        for btn in (self.calib_sp, self.calib_clk_in):
            btn.pack(side=tk.LEFT, padx=3)
        row_c2.pack_forget()

        # 第三列：重連按鈕座標校準
        row_c3 = ttk.Frame(grp_cal)
        row_c3.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(row_c3, text="重連：", width=5, foreground="gray").pack(side=tk.LEFT)
        self.calib_btn_dc  = ttk.Button(row_c3, text="斷線確認",   command=self._calib_btn_disconnect_confirm)
        self.calib_btn_no  = ttk.Button(row_c3, text="系統提示",   command=self._calib_btn_notice_ok)
        self.calib_btn_ot  = ttk.Button(row_c3, text="在線時間",   command=self._calib_btn_online_time_ok)
        self.calib_btn_gs  = ttk.Button(row_c3, text="主畫面開始", command=self._calib_btn_game_start)
        self.calib_btn_li  = ttk.Button(row_c3, text="角色登入",   command=self._calib_btn_login)
        self.calib_btn_qs  = ttk.Button(row_c3, text="快速開始",   command=self._calib_btn_quick_start)
        self.calib_btn_hs  = ttk.Button(row_c3, text="轉轉關閉",   command=self._calib_btn_happy_spin_close)
        self.calib_btn_land = ttk.Button(row_c3, text="地盤",       command=self._calib_btn_land)
        self.calib_btn_lres = ttk.Button(row_c3, text="地盤餐廳",   command=self._calib_btn_land_restaurant)
        for btn in (self.calib_btn_dc, self.calib_btn_no, self.calib_btn_ot,
                    self.calib_btn_gs, self.calib_btn_li, self.calib_btn_qs,
                    self.calib_btn_hs, self.calib_btn_land, self.calib_btn_lres):
            btn.pack(side=tk.LEFT, padx=3)

        # 校準狀態指示列
        self._calib_lbl = {}
        row_cs = ttk.Frame(grp_cal)
        row_cs.pack(fill=tk.X, pady=(3, 4))
        for key, title in (("stoves", "鍋爐"), ("recipe", "食譜"), ("cancel", "彈窗"),
                            ("door", "門口"), ("restaurant", "餐廳"),
                            ("nav", "導航"),
                            ("state", "狀態色"), ("clk_interior", "時鐘內")):
            lbl = ttk.Label(row_cs, text=f"▸{title}", font=("", 8))
            lbl.pack(side=tk.LEFT, padx=(2, 8))
            self._calib_lbl[key] = lbl
        for unused in ("state", "clk_interior"):
            lbl = self._calib_lbl.pop(unused, None)
            if lbl:
                lbl.destroy()
        self._refresh_calib_status()

        # ── 狀態 ─────────────────────────────────────────
        self.status = ttk.Label(f, text="狀態：待機", foreground="gray",
                                font=("", 10, "bold"), anchor=tk.W)
        self.status.pack(fill=tk.X, pady=(2, 6))

        # ── 執行 ─────────────────────────────────────────
        grp_run = ttk.LabelFrame(f, text="執行", padding=(10, 4))
        grp_run.pack(fill=tk.X, pady=(0, 6))
        self.start_btn  = ttk.Button(grp_run, text="▶ 開始",   command=self._start,        width=10)
        self.stop_btn   = ttk.Button(grp_run, text="■ 停止",   command=self._stop,         width=10,
                                     state=tk.DISABLED)
        self.login_btn  = ttk.Button(grp_run, text="↩ 手動登入", command=self._manual_login, width=12)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self.login_btn.pack(side=tk.LEFT, pady=4)

        # ── 工具 ─────────────────────────────────────────
        grp_tool = ttk.LabelFrame(f, text="工具", padding=(10, 4))
        grp_tool.pack(fill=tk.X)
        self.testdet_btn = ttk.Button(grp_tool, text="偵測測試", command=self._open_detect_test)
        self.preview_btn = ttk.Button(grp_tool, text="預覽座標", command=self._preview_coords)
        self.snap_btn    = ttk.Button(grp_tool, text="立即截圖", command=self._take_live_snap)
        self.testnav_btn = ttk.Button(grp_tool, text="測試換頁", command=self._test_navigate)
        self._debug_var  = tk.BooleanVar(value=False)
        self.debug_btn   = ttk.Checkbutton(grp_tool, text="Debug 截圖",
                                           variable=self._debug_var,
                                           command=self._toggle_debug)
        for btn in (self.preview_btn, self.snap_btn,
                    self.testnav_btn, self.debug_btn):
            btn.pack(side=tk.LEFT, padx=3, pady=4)

    def _refresh_calib_status(self):
        """更新校準區域下方的 ✓/✗ 狀態指示"""
        s = self._extra_settings
        checks = {
            "stoves":     self.stoves != DEFAULT_STOVES,
            "recipe":     os.path.exists(CONFIG_FILE),
            "cancel":     (tuple(self.recipe.get("confirm_btn", ())) !=
                           tuple(DEFAULT_RECIPE["confirm_btn"]) or
                           tuple(self.recipe.get("cancel_btn", ())) !=
                           tuple(DEFAULT_RECIPE["cancel_btn"])),
            "state":      bool(s.get("done_hsv_list") or s.get("clock_hsv_list") or
                               s.get("spoiled_hsv_list") or
                               s.get("done_points") or s.get("clock_points") or
                               s.get("spoiled_points") or s.get("done_color") or
                               s.get("clock_color") or s.get("spoiled_color")),
            "clk_interior": bool(s.get("clock_interior_offsets") and
                                  len(s["clock_interior_offsets"]) == len(self.stoves) and
                                  any(o for o in s["clock_interior_offsets"])),
            "door":       bool(s.get("door_out") and s.get("door_in")),
            "restaurant": bool(s.get("restaurant_pt") and s.get("restaurant_color")),
            "nav":        bool(s.get("btn_land") and s.get("btn_land_restaurant")),
        }
        titles = {"stoves": "鍋爐", "recipe": "食譜", "cancel": "彈窗",
                  "state": "狀態色", "clk_interior": "時鐘內",
                  "door": "門口", "restaurant": "餐廳", "nav": "導航"}
        for key, done in checks.items():
            lbl = self._calib_lbl.get(key)
            if not lbl:
                continue
            if done:
                lbl.config(text=f"✓{titles[key]}", foreground="#27ae60")
            else:
                lbl.config(text=f"✗{titles[key]}", foreground="#cc4444")

    def _toggle_debug(self):
        on = self._debug_var.get()
        self.bot._debug = on
        if on:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            messagebox.showinfo("Debug 截圖", f"已開啟，截圖存到：\n{DEBUG_DIR}")
        else:
            messagebox.showinfo("Debug 截圖", "已關閉。")

    def _browse_flash_exe(self):
        path = filedialog.askopenfilename(
            title="選擇 Flash Player",
            filetypes=[("Flash Player", "flashplayer*.exe"), ("執行檔", "*.exe"), ("所有檔案", "*.*")]
        )
        if path:
            self.vars["flash_exe_path"].set(path)

    def _get_settings(self):
        s = {k: v.get() for k, v in self.vars.items()}
        s.update(self._extra_settings)  # 合併 spoiled_color / spoiled_threshold
        return s

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        for btn in (self.start_btn, self.login_btn,
                    self.calib_s, self.calib_r,
                    self.calib_c, self.calib_sp, self.calib_clk_in,
                    self.calib_door, self.calib_rest,
                    self.calib_btn_dc, self.calib_btn_no, self.calib_btn_ot,
                    self.calib_btn_gs, self.calib_btn_li, self.calib_btn_qs, self.calib_btn_hs,
                    self.calib_btn_land, self.calib_btn_lres,
                    self.flash_browse_btn,
                    self.testnav_btn, self.testdet_btn, self.preview_btn, self.snap_btn):
            btn.config(state=sa)
        self.stop_btn.config(state=sb)

    def _save_all(self):
        try:
            save_config(self.stoves, self.recipe, self._get_settings())
            return True
        except Exception as e:
            messagebox.showerror(
                "設定儲存失敗",
                f"設定沒有寫入檔案，請確認檔案沒有被其他程式鎖住：\n{CONFIG_FILE}\n\n{e}",
                parent=self.root,
            )
            return False

    def _start(self):
        if not self._save_all():
            return
        s = self._get_settings()
        self.bot.settings.update(s)   # 同步 UI 設定到 bot（含 full_clock_pct 等）
        scan_secs = s["cook_minutes"] * 60 + s["cook_seconds"]
        self._set_running(True)
        threading.Thread(
            target=self.bot.run,
            args=(s["page"], s["dish"], scan_secs,
                  s["antlag_minutes"], self._on_status),
            daemon=True
        ).start()

    def _stop(self):
        self.bot.stop()
        self.stop_btn.config(state=tk.DISABLED)

    def _get_hwnd(self):
        hwnd = self.bot.find_window()
        if not hwnd:
            messagebox.showerror("錯誤", "找不到 Flash Player 視窗\n請先開啟遊戲")
        return hwnd

    def _preview_coords(self):
        hwnd = self._get_hwnd()
        if not hwnd: return

        win = tk.Toplevel(self.root)
        win.title("座標預覽")
        win.resizable(False, False)

        coord_var = tk.StringVar(value="移動滑鼠查看座標")
        canvas_holder = [None]   # 用 list 讓內層函式可以更新

        def build_preview(hwnd=hwnd):
            try:
                img, game_w, game_h = capture_window(hwnd)
            except Exception as e:
                messagebox.showerror("錯誤", f"截圖失敗：{e}", parent=win)
                return

            from PIL import ImageDraw
            draw  = ImageDraw.Draw(img)
            scale = max(game_w / MOLE_W, game_h / MOLE_H)
            s     = self._extra_settings

            def to_px(mx, my):
                return int(mx * scale), int(my * scale)

            def outlined_text(x, y, text, color):
                """文字加黑邊，讓深淺背景都清楚"""
                for dx, dy in ((-1,-1),(1,-1),(-1,1),(1,1),(0,-1),(0,1),(-1,0),(1,0)):
                    draw.text((x+dx, y+dy), text, fill="black")
                draw.text((x, y), text, fill=color)

            def dot(mx, my, color, label="", r=9):
                x, y = to_px(mx, my)
                draw.ellipse([x-r, y-r, x+r, y+r], fill=color, outline="white", width=2)
                if label:
                    outlined_text(x+r+3, y-8, label, color)

            def square(mx, my, color, label="", r=6):
                x, y = to_px(mx, my)
                draw.rectangle([x-r, y-r, x+r, y+r], fill=color, outline="white", width=2)
                if label:
                    outlined_text(x+r+3, y-8, label, color)

            def diamond(mx, my, color, label="", r=9):
                x, y = to_px(mx, my)
                draw.polygon([(x, y-r),(x+r, y),(x, y+r),(x-r, y)],
                             fill=color, outline="white")
                if label:
                    outlined_text(x+r+3, y-8, label, color)

            # 狀態偵測點（小方塊，畫在鍋爐下層避免遮擋）
            state_cfgs = [
                ("done_points",    "done_color",    "done_offset",    "#f0c040"),
                ("clock_points",   "clock_color",   "clock_offset",   "#e07820"),
                ("spoiled_points", "spoiled_color", "spoiled_offset", "#c04040"),
            ]
            for pts_key, col_key, off_key, color in state_cfgs:
                pts = s.get(pts_key) or []
                off = s.get(off_key) or [0, 0]
                for stx, sty in self.stoves:
                    if pts:
                        for entry in pts:
                            dx, dy = entry[0], entry[1]
                            square(stx+dx, sty+dy, color, r=5)
                    elif s.get(col_key):
                        square(stx+off[0], sty+off[1], color, r=5)

            # 鍋爐（綠圓）
            for i, (stx, sty) in enumerate(self.stoves):
                dot(stx, sty, "#50e050", f"爐{i+1}")

            # 食譜元素
            rc = self.recipe
            dot(*rc["left_arrow"],  "#40d0d0", "←")
            dot(*rc["right_arrow"], "#40d0d0", "→")
            dot(*rc["close"],       "#e04040", "X")
            for i, pt in enumerate(rc["page_tabs"]):
                dot(*pt, "#e0e040", str(i+1))
            for i, pt in enumerate(rc["dishes"]):
                dot(*pt, "#e08040", f"菜{i+1}")
            dot(*rc["check_pt"],                                    "#f0f0f0", "偵測")
            dot(*rc.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"]), "#d060d0", "確認")
            dot(*rc.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"]),  "#9060d0", "取消")

            # 門口（菱形）
            if s.get("door_out"):
                diamond(*s["door_out"],      "#7090ff", "出門")
            if s.get("door_waypoint"):
                diamond(*s["door_waypoint"], "#7090ff", "中途")
            if s.get("door_in"):
                diamond(*s["door_in"],       "#7090ff", "入門")

            # 餐廳確認點（橘紅方塊）
            if s.get("restaurant_pt"):
                square(*s["restaurant_pt"],  "#ff6090", "餐廳", r=8)

            # 登入後導航點
            if s.get("btn_land"):
                dot(*s["btn_land"], "#30a0ff", "地盤")
            if s.get("btn_land_restaurant"):
                dot(*s["btn_land_restaurant"], "#30a0ff", "地盤餐廳")

            # 縮放顯示
            disp_scale = min(900/game_w, 580/game_h, 1.0)
            disp_w = int(game_w * disp_scale)
            disp_h = int(game_h * disp_scale)
            disp   = img.resize((disp_w, disp_h), Image.LANCZOS)
            photo  = ImageTk.PhotoImage(disp)

            # 更新或建立 Canvas
            old = canvas_holder[0]
            if old:
                old.destroy()
            canvas = tk.Canvas(win, width=disp_w, height=disp_h, cursor="crosshair")
            canvas.pack(side=tk.TOP, padx=8, pady=(8, 4))
            canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            canvas.photo = photo
            canvas_holder[0] = canvas

            # 滑鼠移動顯示摩爾座標
            total_scale = scale * disp_scale
            def on_move(event, _ts=total_scale):
                mx = int(event.x / _ts)
                my = int(event.y / _ts)
                coord_var.set(f"摩爾座標：({mx}, {my})")
            canvas.bind("<Motion>", on_move)
            canvas.bind("<Leave>",  lambda e: coord_var.set("移動滑鼠查看座標"))

        # ── 圖例 ──────────────────────────────────────────────
        legend_items = [
            ("#50e050", "● 鍋爐"),
            ("#f0c040", "■ 做完"),
            ("#e07820", "■ 時鐘"),
            ("#c04040", "■ 腐壞"),
            ("#40d0d0", "● 食譜/偵測"),
            ("#e0e040", "● 頁碼"),
            ("#e08040", "● 菜格"),
            ("#d060d0", "● 確認"),
            ("#9060d0", "● 取消"),
            ("#7090ff", "◆ 門口"),
            ("#ff6090", "■ 餐廳"),
            ("#30a0ff", "● 導航"),
        ]
        legend_frame = ttk.Frame(win)
        legend_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 2))
        for color, text in legend_items:
            tk.Label(legend_frame, text=text, fg=color,
                     font=("", 8), bg=win.cget("bg")).pack(side=tk.LEFT, padx=3)

        # 座標顯示 + 重新截圖按鈕
        bottom = ttk.Frame(win)
        bottom.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(0, 8))
        ttk.Label(bottom, textvariable=coord_var,
                  font=("Courier", 9), foreground="gray").pack(side=tk.LEFT)
        ttk.Button(bottom, text="重新截圖",
                   command=lambda: build_preview()).pack(side=tk.RIGHT)

        build_preview()

    # ── 重連座標校準 ──────────────────────────────────────

    def _calib_one_btn(self, title, prompt, settings_key, done_msg):
        """通用：截圖讓使用者點一個按鈕座標，存入 extra_settings。"""
        hwnd = self._get_hwnd()
        if not hwnd: return
        messagebox.showinfo(f"校準 {title}", prompt)
        def _done(pts):
            self._extra_settings[settings_key] = list(pts[0])
            self.bot.settings[settings_key]    = list(pts[0])
            if not self._save_all():
                return
            messagebox.showinfo("完成", f"{done_msg}：{pts[0]}")
        CalibrationWindow(self.root, hwnd, [f"點擊「{title}」按鈕位置"], _done)

    def _calib_btn_disconnect_confirm(self):
        self._calib_one_btn(
            "斷線確認",
            "請讓「本次連接已斷開」彈窗出現在遊戲畫面，\n再按確定截圖，然後點彈窗上的「確認」按鈕。",
            "btn_disconnect_confirm", "斷線確認按鈕")

    def _calib_btn_notice_ok(self):
        self._calib_one_btn(
            "知道了",
            "請讓「系統提示」彈窗出現，\n再按確定截圖，然後點「知道了」按鈕。",
            "btn_notice_ok", "系統提示按鈕")

    def _calib_btn_online_time_ok(self):
        self._calib_one_btn(
            "在線時間",
            "請讓「您累計在線時間已滿...」通知彈窗出現，\n再按確定截圖，然後點「知道了」按鈕。",
            "btn_online_time_ok", "在線時間通知按鈕")

    def _calib_btn_game_start(self):
        self._calib_one_btn(
            "主畫面開始",
            "請切換到遊戲主畫面（摩爾莊園 LOGO 那頁），\n再按確定截圖，然後點「開始」按鈕。",
            "btn_game_start", "主畫面開始按鈕")

    def _calib_btn_login(self):
        self._calib_one_btn(
            "角色登入",
            "請切換到角色選擇（登入）畫面，\n再按確定截圖，然後點「登入」按鈕。",
            "btn_login", "角色登入按鈕")

    def _calib_btn_quick_start(self):
        self._calib_one_btn(
            "快速開始",
            "請切換到選擇伺服器畫面，\n再按確定截圖，然後點「快速開始」按鈕。",
            "btn_quick_start", "快速開始按鈕")

    def _calib_btn_happy_spin_close(self):
        self._calib_one_btn(
            "轉轉關閉",
            "請讓「歡樂轉轉」彈窗出現在遊戲畫面，\n再按確定截圖，然後點彈窗右上方的關閉按鈕。",
            "btn_happy_spin_close", "歡樂轉轉關閉按鈕")

    def _calib_btn_land(self):
        self._calib_one_btn(
            "地盤",
            "請切換到已進入遊戲的場景，\n再按確定截圖，然後點右下角「地盤」按鈕。",
            "btn_land", "地盤按鈕")

    def _calib_btn_land_restaurant(self):
        self._calib_one_btn(
            "地盤餐廳",
            "請先點開右下角「地盤」，讓餐廳目標出現在畫面上，\n再按確定截圖，然後點「餐廳」的位置。",
            "btn_land_restaurant", "地盤餐廳按鈕")

    def _manual_login(self):
        """手動觸發登入流程（不啟動完整掃描），用於測試或手動重連。"""
        if not self._save_all():
            return
        self.bot.settings.update(self._get_settings())
        self.bot._stop.clear()
        self._set_running(True)
        def _run():
            try:
                hwnd = self.bot.find_window()
                if hwnd:
                    self.bot.hwnd = hwnd
                    self.bot._login_flow(self._on_status)
                else:
                    self._on_status("找不到 Flash Player 視窗，嘗試自動開啟…")
                    self.bot._launch_flash_and_login(self._on_status)
            finally:
                self.root.after(0, lambda: self._set_running(False))
        threading.Thread(target=_run, daemon=True).start()

    def _calib_cancel(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        messagebox.showinfo(
            "校準彈窗按鈕",
            "請先點任意一個鍋爐，讓「捐菜給拉姆」彈窗出現，\n再回到這裡點「確定」開始校準。\n\n"
            "截圖後依序點：\n"
            "①「確認」按鈕（清除腐壞食物用）\n"
            "②「取消」按鈕（做菜中退出用）"
        )
        CalibrationWindow(self.root, hwnd, ["① 確認按鈕", "② 取消按鈕"], self._done_cancel)

    def _done_cancel(self, pts):
        self.recipe["confirm_btn"] = pts[0]
        self.recipe["cancel_btn"]  = pts[1]
        self.bot.recipe = self.recipe
        if not self._save_all():
            return
        self._refresh_calib_status()
        messagebox.showinfo("完成", f"確認：{pts[0]}　取消：{pts[1]}\n已儲存。")

    def _test_ocr(self):
        """截圖目前彈窗區域，執行 OCR，顯示辨識結果供確認關鍵字是否正確。
        OCR 在背景執行緒跑，避免阻塞 UI。"""
        hwnd = self._get_hwnd()
        if not hwnd: return
        self.bot.hwnd = hwnd
        region = self.bot._capture_popup_region()
        if region is None:
            messagebox.showerror("測 OCR", "截圖失敗，請確認遊戲視窗已開啟。")
            return

        self.calib_ocr.config(state="disabled", text="辨識中…")

        def _run():
            text = self.bot._ocr_image(region)

            def _show():
                self.calib_ocr.config(state="normal", text="測 OCR")
                if not text:
                    messagebox.showwarning(
                        "測 OCR",
                        "OCR 沒有辨識到文字。\n\n"
                        "可能原因：\n"
                        "• 目前畫面沒有彈窗\n"
                        "• Windows 未安裝中文 OCR 語言包\n"
                        "• winsdk 未安裝"
                    )
                    return
                if any(kw in text for kw in ["燒糊", "處理掉", "燒"]):
                    result = "→ 判定：燒糊彈窗（會按確認清除）"
                elif any(kw in text for kw in ["捐", "流浪", "拉姆"]):
                    result = "→ 判定：捐菜彈窗（會按取消跳過）"
                else:
                    result = "→ 判定：無法辨識（會走保守策略）"
                messagebox.showinfo(
                    "測 OCR 結果",
                    f"辨識到的文字：\n\n「{text.strip()}」\n\n{result}"
                )

            self.root.after(0, _show)

        threading.Thread(target=_run, daemon=True).start()

    def _calib_door(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        messagebox.showinfo(
            "校準門口",
            "步驟一：請先截圖校準「出口」（點餐廳內的上方門口）。\n"
            "步驟二：手動走出去後，再按一次此按鈕校準「入口」。\n\n"
            "現在先校準「出口」位置。"
        )
        CalibrationWindow(self.root, hwnd, ["出口（餐廳內的上方門口）"], self._done_door_out)

    def _done_door_out(self, pts):
        self._extra_settings["door_out"] = list(pts[0])
        self.bot.settings["door_out"] = list(pts[0])
        if not self._save_all():
            return

        # 問要不要校準中途走動點
        ans = messagebox.askyesno(
            "中途走動點",
            f"出口已儲存：{pts[0]}\n\n"
            "出門後需要先走到旁邊再進入嗎？\n\n"
            "【是】→ 多校準一個「走到入口前的中途點」\n"
            "【否】→ 跳過，直接校準入口"
        )
        if ans:
            messagebox.showinfo(
                "校準中途走動點",
                "請先手動走出餐廳，\n"
                "站到入口附近的位置後，\n"
                "再回來按「確定」截圖校準。\n\n"
                "截圖後點一下角色要走到的目標位置。"
            )
            hwnd = self._get_hwnd()
            if hwnd:
                CalibrationWindow(self.root, hwnd, ["中途走動點（走到入口附近）"], self._done_door_waypoint)
        else:
            # 清除舊的 waypoint（如果之前設過）
            self._extra_settings["door_waypoint"] = None
            self.bot.settings["door_waypoint"] = None
            if not self._save_all():
                return
            if messagebox.askyesno("繼續", "請手動走出餐廳後，按「是」截圖校準入口。"):
                hwnd = self._get_hwnd()
                if hwnd:
                    CalibrationWindow(self.root, hwnd, ["入口（餐廳外往內的門口）"], self._done_door_in)

    def _done_door_waypoint(self, pts):
        self._extra_settings["door_waypoint"] = list(pts[0])
        self.bot.settings["door_waypoint"] = list(pts[0])
        if not self._save_all():
            return
        if messagebox.askyesno("繼續", f"走動點已儲存：{pts[0]}\n\n請走到入口位置後，按「是」截圖校準入口。"):
            hwnd = self._get_hwnd()
            if hwnd:
                CalibrationWindow(self.root, hwnd, ["入口（餐廳外往內的門口）"], self._done_door_in)

    def _done_door_in(self, pts):
        self._extra_settings["door_in"] = list(pts[0])
        self.bot.settings["door_in"] = list(pts[0])
        if not self._save_all():
            return
        self._refresh_calib_status()
        wp = self._extra_settings.get("door_waypoint")
        extra = f"\n中途走動點：{wp}" if wp else ""
        messagebox.showinfo("完成", f"入口已儲存：{pts[0]}{extra}\n防卡頓將改用門口出入。")

    def _calib_restaurant(self):
        """
        校準「在餐廳內」的判斷點：讓使用者在餐廳內截圖並點一個
        靜態固定顏色的位置（例如固定背景牆、地板）作為基準。
        """
        hwnd = self._get_hwnd()
        if not hwnd: return

        # 說明目前校準狀態
        pt    = self._extra_settings.get("restaurant_pt")
        color = self._extra_settings.get("restaurant_color")
        current = f"目前：{pt}  RGB{tuple(color)}" if pt and color else "目前：未校準"

        messagebox.showinfo(
            "校準餐廳確認點",
            f"{current}\n\n"
            "請先確認現在在餐廳內，再點「確定」截圖。\n\n"
            "截圖後，點一個畫面中【固定不變的背景點】\n"
            "（例如固定的牆壁、地板顏色，不要點鍋爐或角色）。\n\n"
            "機器人會用這個點的顏色判斷是否在餐廳。"
        )
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}")
            return

        sg = max(game_w / MOLE_W, game_h / MOLE_H)
        disp_scale = min(900 / game_w, 580 / game_h, 1.0)
        disp  = img.resize((int(game_w * disp_scale), int(game_h * disp_scale)))
        photo = ImageTk.PhotoImage(disp)

        win = tk.Toplevel(self.root)
        win.title("校準餐廳確認點")
        win.grab_set()
        ttk.Label(win, text="▶ 點一個餐廳內的固定背景點（牆壁/地板等靜態位置）",
                  padding=8).pack()
        canvas = tk.Canvas(win,
                           width=int(game_w * disp_scale),
                           height=int(game_h * disp_scale),
                           cursor="crosshair")
        canvas.pack(padx=8, pady=8)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.photo = photo

        def on_pick(event):
            px  = min(int(event.x / disp_scale), game_w - 1)
            py  = min(int(event.y / disp_scale), game_h - 1)
            mx  = int(px / sg)
            my  = int(py / sg)
            rgb = img.convert("RGB").getpixel((px, py))
            self._extra_settings["restaurant_pt"]    = [mx, my]
            self._extra_settings["restaurant_color"] = list(rgb)
            self.bot.settings["restaurant_pt"]    = [mx, my]
            self.bot.settings["restaurant_color"] = list(rgb)
            if not self._save_all():
                return
            self._refresh_calib_status()
            win.destroy()
            messagebox.showinfo("完成",
                f"餐廳確認點：({mx}, {my})  RGB{rgb}\n已儲存。\n\n"
                "機器人每輪掃描前會確認這個顏色，\n不在餐廳時會自動嘗試回去。")

        canvas.bind("<Button-1>", on_pick)

    def _calib_clock_interior(self):
        """
        時鐘內部校準：為每個鍋爐設定時鐘橙色環內側的偵測點。
        偵測白色像素佔比，區分「烹飪中（有白色扇形）」vs「菜做好（全填滿）」。
        建議在食物烹飪中截圖，點擊橙色環內側的粉紅或白色區域。
        """
        self._calib_interior_generic(
            offsets_key="clock_interior_offsets",
            title="時鐘內部偵測點",
            hint="請在烹飪中，點擊時鐘橙色環的內側（粉紅色或白色扇形區域，非橙色邊框）",
            check_fn=lambda v, s: (v > 60),       # 內部應該是亮的（粉紅或白）
            expect_desc="粉紅/白色（V > 60%）",
        )

    def _calib_interior_generic(self, offsets_key, title, hint, check_fn, expect_desc):
        """
        通用「各爐獨立偏移」校準視窗（用於時鐘內部、黑煙等單點偏移類型）。
        check_fn(v, s) → bool：點的顏色是否合理，不合理時顯示警告。
        """
        n = len(self.stoves)
        if n == 0:
            messagebox.showwarning("提示", "請先校準鍋爐座標。")
            return
        hwnd = self._get_hwnd()
        if not hwnd: return
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}"); return

        sg      = max(game_w / MOLE_W, game_h / MOLE_H)
        img_rgb = img.convert("RGB")

        LEFT_MAX_W, LEFT_MAX_H = 480, 400
        left_scale = min(LEFT_MAX_W / game_w, LEFT_MAX_H / game_h, 1.0)
        lw = int(game_w * left_scale)
        lh = int(game_h * left_scale)
        left_photo = ImageTk.PhotoImage(img.resize((lw, lh), Image.LANCZOS))

        ZOOM_R      = 60
        ZOOM_SIZE   = 320
        zoom_factor = ZOOM_SIZE / (ZOOM_R * 2)

        offsets = [None] * n
        cur     = [0]

        ex = self._extra_settings.get(offsets_key) or []
        if len(ex) == n:
            for i in range(n):
                offsets[i] = list(ex[i]) if ex[i] else None

        win = tk.Toplevel(self.root)
        win.title(f"校準「{title}」（各鍋爐獨立）")
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win, text=hint,
                  font=("", 11, "bold"), padding=(8, 8, 8, 2)).pack()
        ttk.Label(win, text=f"合理顏色：{expect_desc}",
                  foreground="gray", padding=(8, 0, 8, 4), wraplength=820).pack()

        sel_row = ttk.Frame(win)
        sel_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Label(sel_row, text="切換鍋爐：").pack(side=tk.LEFT)
        stove_btns = []
        for i in range(n):
            b = tk.Button(sel_row, text=f"爐{i+1}  ——", width=10,
                          font=("", 9), relief=tk.RAISED,
                          command=lambda idx=i: select_stove(idx))
            b.pack(side=tk.LEFT, padx=2)
            stove_btns.append(b)

        panels = ttk.Frame(win)
        panels.pack(padx=8, pady=4)

        lf = ttk.LabelFrame(panels, text="全景（點鍋爐圓圈切換，或直接點擊校準）")
        lf.pack(side=tk.LEFT, padx=(0, 8), anchor=tk.N)
        left_canvas = tk.Canvas(lf, width=lw, height=lh, cursor="crosshair")
        left_canvas.pack()
        left_canvas.create_image(0, 0, anchor=tk.NW, image=left_photo)
        left_canvas.photo = left_photo

        rf = ttk.LabelFrame(panels, text="放大圖（在此點擊校準）")
        rf.pack(side=tk.LEFT, anchor=tk.N)
        zoom_canvas = tk.Canvas(rf, width=ZOOM_SIZE, height=ZOOM_SIZE,
                                cursor="crosshair", bg="#1a1a1a")
        zoom_canvas.pack()
        info_lbl = ttk.Label(rf, text="請選擇要校準的鍋爐",
                             foreground="gray", padding=(4, 2),
                             font=("", 9), wraplength=ZOOM_SIZE)
        info_lbl.pack()

        stove_ovals = []
        for i, (sx2, sy2) in enumerate(self.stoves):
            ec = int(sx2 * sg * left_scale)
            ey = int(sy2 * sg * left_scale)
            ov = left_canvas.create_oval(ec-12, ey-12, ec+12, ey+12, outline="gray", width=2)
            tx = left_canvas.create_text(ec, ey, text=str(i+1),
                                         fill="gray", font=("Arial", 9, "bold"))
            stove_ovals.append((ov, tx))

        zoom_photo_ref = [None]

        def _get_pixel_info(i):
            off = offsets[i]
            if not off: return None, None
            sx2, sy2 = self.stoves[i]
            px_ = min(max(int((sx2 + off[0]) * sg), 0), game_w - 1)
            py_ = min(max(int((sy2 + off[1]) * sg), 0), game_h - 1)
            r, g2, b = img_rgb.getpixel((px_, py_))
            _, s_, v_ = _rgb_to_hsv(r, g2, b)
            return v_, s_

        def update_stove_btn(i):
            off = offsets[i]
            if off is None:
                txt, fg, bg = f"爐{i+1}  ——", "gray", "SystemButtonFace"
            else:
                v_, s_ = _get_pixel_info(i)
                ok = check_fn(v_, s_) if v_ is not None else False
                mark = "✓" if ok else "⚠"
                txt  = f"爐{i+1} V={v_:.0f}{mark}"
                fg   = "#1a7a1a" if ok else "#8a4a00"
                bg   = "#d4f5d4" if ok else "#fff0c0"
            stove_btns[i].config(text=txt, fg=fg, bg=bg,
                                 relief=tk.SUNKEN if i == cur[0] else tk.RAISED)

        def update_left_markers():
            for i, (ov, tx) in enumerate(stove_ovals):
                if i == cur[0]:
                    col, ww = "#00dd00", 3
                elif offsets[i] is None:
                    col, ww = "gray", 2
                else:
                    v_, s_ = _get_pixel_info(i)
                    col = "#27ae60" if (v_ is not None and check_fn(v_, s_)) else "orange"
                    ww  = 2
                left_canvas.itemconfig(ov, outline=col, width=ww)
                left_canvas.itemconfig(tx, fill=col)

        def show_zoom(i, dot_mx=None, dot_my=None):
            sx2, sy2 = self.stoves[i]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            px0 = min(max(int(mx0 * sg), 0), game_w)
            py0 = min(max(int(my0 * sg), 0), game_h)
            px1 = min(int((mx0 + ZOOM_R * 2) * sg), game_w)
            py1 = min(int((my0 + ZOOM_R * 2) * sg), game_h)
            z = img_rgb.crop((px0, py0, px1, py1)).resize(
                    (ZOOM_SIZE, ZOOM_SIZE), Image.LANCZOS)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(z)
            cx_c = int((sx2 - mx0) * zoom_factor)
            cy_c = int((sy2 - my0) * zoom_factor)
            draw.line([(cx_c-14, cy_c), (cx_c+14, cy_c)], fill="#ffffff", width=1)
            draw.line([(cx_c, cy_c-14), (cx_c, cy_c+14)], fill="#ffffff", width=1)
            if offsets[i]:
                dx_c = int((sx2 + offsets[i][0] - mx0) * zoom_factor)
                dy_c = int((sy2 + offsets[i][1] - my0) * zoom_factor)
                draw.ellipse([dx_c-8, dy_c-8, dx_c+8, dy_c+8], outline="white", width=2)
            if dot_mx is not None:
                dx_c = int((dot_mx - mx0) * zoom_factor)
                dy_c = int((dot_my - my0) * zoom_factor)
                draw.ellipse([dx_c-9, dy_c-9, dx_c+9, dy_c+9], outline="cyan", width=3)
                draw.line([(dx_c-14, dy_c), (dx_c+14, dy_c)], fill="cyan", width=2)
                draw.line([(dx_c, dy_c-14), (dx_c, dy_c+14)], fill="cyan", width=2)
            photo = ImageTk.PhotoImage(z)
            zoom_canvas.delete("all")
            zoom_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            zoom_canvas.photo = photo
            zoom_photo_ref[0] = photo

        def show_info(i, v_=None, s_=None):
            off = offsets[i]
            if off is None:
                info_lbl.config(text=f"鍋爐 {i+1}：尚未校準", foreground="gray"); return
            if v_ is None:
                v_, s_ = _get_pixel_info(i)
            if v_ is None:
                info_lbl.config(text=f"鍋爐 {i+1}：讀取失敗", foreground="gray"); return
            ok = check_fn(v_, s_)
            color_name = _hsv_color_name(0, s_, v_)
            status = f"✓ 顏色合理（{color_name}，V={v_:.0f}）" if ok else \
                     f"⚠ 顏色可能不對（{color_name}，V={v_:.0f}），期望：{expect_desc}"
            info_lbl.config(text=f"鍋爐 {i+1}：偏移 {off}\n{status}",
                            foreground="#27ae60" if ok else "orange")

        def select_stove(i):
            cur[0] = i
            show_zoom(i)
            show_info(i)
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        for i in range(n): update_stove_btn(i)
        select_stove(0)

        def _do_pick(click_mx, click_my):
            i = cur[0]
            sx2, sy2 = self.stoves[i]
            click_px = min(max(int(click_mx * sg), 0), game_w - 1)
            click_py = min(max(int(click_my * sg), 0), game_h - 1)
            r, g2, b = img_rgb.getpixel((click_px, click_py))
            _, s_, v_ = _rgb_to_hsv(r, g2, b)
            dx = round(click_mx - sx2); dy = round(click_my - sy2)
            offsets[i] = [dx, dy]
            show_zoom(i, click_mx, click_my)
            show_info(i, v_, s_)
            for j in range(n): update_stove_btn(j)
            update_left_markers()
            def auto_next():
                for j in range(1, n + 1):
                    nxt = (i + j) % n
                    if offsets[nxt] is None:
                        select_stove(nxt); return
                info_lbl.config(text=f"全部 {n} 個鍋爐已校準！", foreground="#27ae60")
            win.after(600, auto_next)

        def on_zoom_click(event):
            sx2, sy2 = self.stoves[cur[0]]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            _do_pick(mx0 + event.x / zoom_factor, my0 + event.y / zoom_factor)

        def on_left_click(event):
            click_mx = (event.x / left_scale) / sg
            click_my = (event.y / left_scale) / sg
            for i, (sx2, sy2) in enumerate(self.stoves):
                if ((click_mx - sx2)**2 + (click_my - sy2)**2) ** 0.5 < 20:
                    select_stove(i); return
            _do_pick(click_mx, click_my)

        zoom_canvas.bind("<Button-1>", on_zoom_click)
        left_canvas.bind("<Button-1>", on_left_click)

        nav_frame = ttk.Frame(win)
        nav_frame.pack(pady=(4, 0))
        ttk.Button(nav_frame, text="◀ 上一爐",
                   command=lambda: select_stove((cur[0]-1)%n)).pack(side=tk.LEFT, padx=8)
        ttk.Button(nav_frame, text="下一爐 ▶",
                   command=lambda: select_stove((cur[0]+1)%n)).pack(side=tk.LEFT, padx=8)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)

        def on_save():
            missing = [i+1 for i in range(n) if offsets[i] is None]
            if missing:
                messagebox.showwarning("提示", f"鍋爐 {missing} 尚未校準。"); return
            self._extra_settings[offsets_key] = list(offsets)
            self.bot.settings[offsets_key]    = list(offsets)
            if not self._save_all():
                return
            self._refresh_calib_status()
            win.destroy()
            messagebox.showinfo("完成", f"「{title}」已儲存 {n} 個校準點。")

        def on_clear_one():
            i = cur[0]; offsets[i] = None
            show_zoom(i)
            info_lbl.config(text=f"鍋爐 {i+1} 已清除", foreground="gray")
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        def on_clear_all():
            for i in range(n): offsets[i] = None
            self._extra_settings[offsets_key] = []
            self.bot.settings[offsets_key]    = []
            if not self._save_all():
                return
            info_lbl.config(text="已清空", foreground="gray")
            for j in range(n): update_stove_btn(j)
            select_stove(cur[0])

        ttk.Button(btn_frame, text="儲存",     command=on_save     ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除此爐", command=on_clear_one).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除全部", command=on_clear_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消",     command=win.destroy ).pack(side=tk.LEFT, padx=6)

    def _calib_smoke(self):
        """
        黑煙校準：為每個鍋爐獨立設定黑煙偵測點偏移。
        點擊放大圖 → 記錄該點相對鍋爐中心的 [dx,dy] 與當下亮度（V）。
        """
        n = len(self.stoves)
        if n == 0:
            messagebox.showwarning("提示", "請先校準鍋爐座標。")
            return
        hwnd = self._get_hwnd()
        if not hwnd: return
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}"); return

        sg      = max(game_w / MOLE_W, game_h / MOLE_H)
        img_rgb = img.convert("RGB")
        threshold = self._extra_settings.get("smoke_threshold", 30)

        LEFT_MAX_W, LEFT_MAX_H = 480, 400
        left_scale = min(LEFT_MAX_W / game_w, LEFT_MAX_H / game_h, 1.0)
        lw = int(game_w * left_scale)
        lh = int(game_h * left_scale)
        left_photo = ImageTk.PhotoImage(img.resize((lw, lh), Image.LANCZOS))

        ZOOM_R      = 60
        ZOOM_SIZE   = 320
        zoom_factor = ZOOM_SIZE / (ZOOM_R * 2)

        # 每個鍋爐的偏移（None = 未校準）
        offsets = [None] * n
        cur     = [0]

        # 載入既有校準
        ex = self._extra_settings.get("smoke_offsets") or []
        if len(ex) == n:
            for i in range(n):
                offsets[i] = list(ex[i]) if ex[i] else None

        win = tk.Toplevel(self.root)
        win.title("校準黑煙偵測點（各鍋爐獨立）")
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win,
            text="在燒糊狀態下截圖，對每個鍋爐點擊黑煙最濃的位置",
            font=("", 11, "bold"), padding=(8, 8, 8, 2)).pack()
        ttk.Label(win,
            text="V（亮度）< 閾值 → 判定有黑煙。閾值越低越嚴格，建議從 30 開始。",
            foreground="gray", padding=(8, 0, 8, 4), wraplength=820).pack()

        # 頂部鍋爐切換
        sel_row = ttk.Frame(win)
        sel_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Label(sel_row, text="切換鍋爐：").pack(side=tk.LEFT)
        stove_btns = []
        for i in range(n):
            b = tk.Button(sel_row, text=f"爐{i+1}  ——", width=10,
                          font=("", 9), relief=tk.RAISED,
                          command=lambda idx=i: select_stove(idx))
            b.pack(side=tk.LEFT, padx=2)
            stove_btns.append(b)

        # 雙面板
        panels = ttk.Frame(win)
        panels.pack(padx=8, pady=4)

        lf = ttk.LabelFrame(panels, text="全景（點鍋爐圓圈切換，或直接點擊校準）")
        lf.pack(side=tk.LEFT, padx=(0, 8), anchor=tk.N)
        left_canvas = tk.Canvas(lf, width=lw, height=lh, cursor="crosshair")
        left_canvas.pack()
        left_canvas.create_image(0, 0, anchor=tk.NW, image=left_photo)
        left_canvas.photo = left_photo

        rf = ttk.LabelFrame(panels, text="放大圖（在此點擊校準黑煙位置）")
        rf.pack(side=tk.LEFT, anchor=tk.N)
        zoom_canvas = tk.Canvas(rf, width=ZOOM_SIZE, height=ZOOM_SIZE,
                                cursor="crosshair", bg="#1a1a1a")
        zoom_canvas.pack()
        info_lbl = ttk.Label(rf, text="請選擇要校準的鍋爐",
                             foreground="gray", padding=(4, 2),
                             font=("", 9), wraplength=ZOOM_SIZE)
        info_lbl.pack()

        stove_ovals = []
        for i, (sx2, sy2) in enumerate(self.stoves):
            ex_c = int(sx2 * sg * left_scale)
            ey_c = int(sy2 * sg * left_scale)
            ov = left_canvas.create_oval(ex_c-12, ey_c-12, ex_c+12, ey_c+12,
                                         outline="gray", width=2)
            tx = left_canvas.create_text(ex_c, ey_c, text=str(i+1),
                                         fill="gray", font=("Arial", 9, "bold"))
            stove_ovals.append((ov, tx))

        zoom_photo_ref = [None]

        def update_stove_btn(i):
            off = offsets[i]
            if off is None:
                txt, fg, bg = f"爐{i+1}  ——", "gray", "SystemButtonFace"
            else:
                sx2, sy2 = self.stoves[i]
                px_ = min(max(int((sx2 + off[0]) * sg), 0), game_w - 1)
                py_ = min(max(int((sy2 + off[1]) * sg), 0), game_h - 1)
                r, g, b = img_rgb.getpixel((px_, py_))
                _, _, v = _rgb_to_hsv(r, g, b)
                has = v < threshold
                mark = "✓" if has else "⚠"
                txt  = f"爐{i+1} V={v:.0f}{mark}"
                fg   = "#1a7a1a" if has else "#8a4a00"
                bg   = "#d4f5d4" if has else "#fff0c0"
            stove_btns[i].config(text=txt, fg=fg, bg=bg,
                                 relief=tk.SUNKEN if i == cur[0] else tk.RAISED)

        def update_left_markers():
            for i, (ov, tx) in enumerate(stove_ovals):
                if i == cur[0]:
                    col, ww = "#00dd00", 3
                elif offsets[i] is None:
                    col, ww = "gray", 2
                else:
                    sx2, sy2 = self.stoves[i]
                    px_ = min(max(int((sx2 + offsets[i][0]) * sg), 0), game_w - 1)
                    py_ = min(max(int((sy2 + offsets[i][1]) * sg), 0), game_h - 1)
                    r, g, b = img_rgb.getpixel((px_, py_))
                    _, _, v = _rgb_to_hsv(r, g, b)
                    col = "#27ae60" if v < threshold else "orange"
                    ww  = 2
                left_canvas.itemconfig(ov, outline=col, width=ww)
                left_canvas.itemconfig(tx, fill=col)

        def show_zoom(i, dot_mx=None, dot_my=None):
            sx2, sy2 = self.stoves[i]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            px0 = min(max(int(mx0 * sg), 0), game_w)
            py0 = min(max(int(my0 * sg), 0), game_h)
            px1 = min(int((mx0 + ZOOM_R * 2) * sg), game_w)
            py1 = min(int((my0 + ZOOM_R * 2) * sg), game_h)
            z = img_rgb.crop((px0, py0, px1, py1)).resize(
                    (ZOOM_SIZE, ZOOM_SIZE), Image.LANCZOS)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(z)
            cx_c = int((sx2 - mx0) * zoom_factor)
            cy_c = int((sy2 - my0) * zoom_factor)
            draw.line([(cx_c-14, cy_c), (cx_c+14, cy_c)], fill="#ffffff", width=1)
            draw.line([(cx_c, cy_c-14), (cx_c, cy_c+14)], fill="#ffffff", width=1)
            # 已校準的點（白框）
            if offsets[i]:
                dx_c = int((sx2 + offsets[i][0] - mx0) * zoom_factor)
                dy_c = int((sy2 + offsets[i][1] - my0) * zoom_factor)
                draw.ellipse([dx_c-8, dy_c-8, dx_c+8, dy_c+8], outline="white", width=2)
            if dot_mx is not None:
                dx_c = int((dot_mx - mx0) * zoom_factor)
                dy_c = int((dot_my - my0) * zoom_factor)
                draw.ellipse([dx_c-9, dy_c-9, dx_c+9, dy_c+9], outline="red", width=3)
                draw.line([(dx_c-14, dy_c), (dx_c+14, dy_c)], fill="red", width=2)
                draw.line([(dx_c, dy_c-14), (dx_c, dy_c+14)], fill="red", width=2)
            photo = ImageTk.PhotoImage(z)
            zoom_canvas.delete("all")
            zoom_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            zoom_canvas.photo = photo
            zoom_photo_ref[0] = photo

        def show_info(i, v=None):
            off = offsets[i]
            if off is None:
                info_lbl.config(text=f"鍋爐 {i+1}：尚未校準", foreground="gray")
                return
            if v is None:
                sx2, sy2 = self.stoves[i]
                px_ = min(max(int((sx2 + off[0]) * sg), 0), game_w - 1)
                py_ = min(max(int((sy2 + off[1]) * sg), 0), game_h - 1)
                r, g2, b = img_rgb.getpixel((px_, py_))
                _, _, v = _rgb_to_hsv(r, g2, b)
            has = v < threshold
            status = f"✓ 偵測到黑煙（V={v:.0f} < {threshold}）" if has else \
                     f"⚠ 未偵測到黑煙（V={v:.0f} ≥ {threshold}，建議重選或提高閾值）"
            info_lbl.config(text=f"鍋爐 {i+1}：偏移 {off}\n{status}",
                            foreground="#27ae60" if has else "orange")

        def select_stove(i):
            cur[0] = i
            show_zoom(i)
            show_info(i)
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        for i in range(n): update_stove_btn(i)
        select_stove(0)

        def _do_pick(click_mx, click_my):
            i = cur[0]
            sx2, sy2 = self.stoves[i]
            click_px = min(max(int(click_mx * sg), 0), game_w - 1)
            click_py = min(max(int(click_my * sg), 0), game_h - 1)
            r, g2, b = img_rgb.getpixel((click_px, click_py))
            _, _, v = _rgb_to_hsv(r, g2, b)
            dx = round(click_mx - sx2); dy = round(click_my - sy2)
            offsets[i] = [dx, dy]
            show_zoom(i, click_mx, click_my)
            show_info(i, v)
            for j in range(n): update_stove_btn(j)
            update_left_markers()
            # 自動跳下一個尚未校準的鍋爐
            def auto_next():
                for j in range(1, n + 1):
                    nxt = (i + j) % n
                    if offsets[nxt] is None:
                        select_stove(nxt); return
                info_lbl.config(text=f"全部 {n} 個鍋爐已校準！確認後按儲存。",
                                foreground="#27ae60")
            win.after(600, auto_next)

        def on_zoom_click(event):
            sx2, sy2 = self.stoves[cur[0]]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            _do_pick(mx0 + event.x / zoom_factor, my0 + event.y / zoom_factor)

        def on_left_click(event):
            click_mx = (event.x / left_scale) / sg
            click_my = (event.y / left_scale) / sg
            for i, (sx2, sy2) in enumerate(self.stoves):
                if ((click_mx - sx2)**2 + (click_my - sy2)**2) ** 0.5 < 20:
                    select_stove(i); return
            _do_pick(click_mx, click_my)

        zoom_canvas.bind("<Button-1>", on_zoom_click)
        left_canvas.bind("<Button-1>", on_left_click)

        # ── 閾值調整 ───────────────────────────────────────
        thr_row = ttk.Frame(win)
        thr_row.pack(pady=(2, 0))
        ttk.Label(thr_row, text="黑煙亮度閾值 V <").pack(side=tk.LEFT)
        thr_var = tk.IntVar(value=threshold)
        thr_spin = ttk.Spinbox(thr_row, from_=5, to=80, textvariable=thr_var, width=5)
        thr_spin.pack(side=tk.LEFT, padx=4)
        ttk.Label(thr_row, text="（值越小越嚴格）").pack(side=tk.LEFT)

        nav_frame = ttk.Frame(win)
        nav_frame.pack(pady=(4, 0))
        ttk.Button(nav_frame, text="◀ 上一爐",
                   command=lambda: select_stove((cur[0] - 1) % n)).pack(side=tk.LEFT, padx=8)
        ttk.Button(nav_frame, text="下一爐 ▶",
                   command=lambda: select_stove((cur[0] + 1) % n)).pack(side=tk.LEFT, padx=8)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)

        def on_save():
            missing = [i+1 for i in range(n) if offsets[i] is None]
            if missing:
                messagebox.showwarning("提示", f"鍋爐 {missing} 尚未校準。"); return
            thr = thr_var.get()
            self._extra_settings["smoke_offsets"]   = list(offsets)
            self._extra_settings["smoke_threshold"]  = thr
            self.bot.settings["smoke_offsets"]       = list(offsets)
            self.bot.settings["smoke_threshold"]     = thr
            if not self._save_all():
                return
            self._refresh_calib_status()
            win.destroy()
            messagebox.showinfo("完成", f"黑煙校準已儲存（閾值 V < {thr}）。")

        def on_clear_one():
            i = cur[0]
            offsets[i] = None
            show_zoom(i)
            info_lbl.config(text=f"鍋爐 {i+1} 已清除，請重新點選", foreground="gray")
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        def on_clear_all():
            for i in range(n): offsets[i] = None
            self._extra_settings["smoke_offsets"] = []
            self.bot.settings["smoke_offsets"]    = []
            if not self._save_all():
                return
            info_lbl.config(text="已清空所有黑煙校準點", foreground="gray")
            for j in range(n): update_stove_btn(j)
            select_stove(cur[0])

        ttk.Button(btn_frame, text="儲存",     command=on_save     ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除此爐", command=on_clear_one).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除全部", command=on_clear_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消",     command=win.destroy ).pack(side=tk.LEFT, padx=6)

    def _calib_state_colors(self):
        """開啟鍋爐狀態顏色校準選擇器"""
        win = tk.Toplevel(self.root)
        win.title("校準鍋爐狀態")
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win, text="選擇要校準的鍋爐狀態：", padding=(12, 10, 12, 2)).pack()
        ttk.Label(
            win,
            text="校準越多狀態，機器人判斷越準確。",
            foreground="gray", padding=(12, 0, 12, 8)
        ).pack()

        # (顯示名稱, 說明, 顏色key, 偏移key或None)
        states = [
            ("時鐘（烹飪）", "橙色圓形時鐘 → 烹飪中跳過",     "clock_color",   "clock_offset"),
            ("做完（黃光）", "食物做好黃光 → 自動收菜再重做", "done_color",    "done_offset"),
        ]

        for label, hint, color_key, offset_key in states:
            state_name = color_key.replace("_color", "")
            hsv_list = self._extra_settings.get(f"{state_name}_hsv_list") or []
            points   = self._extra_settings.get(f"{state_name}_points") or []
            color    = self._extra_settings.get(color_key)
            offset   = self._extra_settings.get(offset_key) if offset_key else None
            n_stoves = len(self.stoves)
            if hsv_list:
                badge = f"✓ HSV 區域（{len(hsv_list)} 爐）"
            elif points:
                if len(points) == n_stoves:
                    badge = f"✓ 各鍋爐獨立（{len(points)} 點）"
                else:
                    badge = f"✓ 共用模式（{len(points)} 點）"
            elif color:
                badge = f"✓ RGB{tuple(color)}"
                if offset:
                    badge += f"  偏移{tuple(offset)}"
            else:
                badge = "未校準"

            row = ttk.Frame(win)
            row.pack(fill=tk.X, padx=12, pady=3)
            ttk.Button(
                row, text=f"校準「{label}」",
                command=lambda ck=color_key, ok=offset_key, l=label, w=win: (
                    w.destroy(),
                    self._calib_offset_color(ck, ok, l)
                )
            ).pack(side=tk.LEFT)
            ttk.Label(row, text=f"  {hint}  [{badge}]", foreground="gray").pack(side=tk.LEFT)

        ttk.Button(win, text="關閉", command=win.destroy).pack(pady=8)

    def _calib_offset_color(self, color_key, offset_key, label):
        """
        個別校準（放大圖版）：左側顯示全景，右側顯示放大圖，
        點擊右側放大圖完成校準，同時儲存 RGB (*_points) 與 HSV (*_hsv_list)。
        """
        state_name = color_key.replace("_color", "")
        points_key = f"{state_name}_points"
        hsv_list_key = f"{state_name}_hsv_list"
        n = len(self.stoves)
        if n == 0:
            messagebox.showwarning("提示", "請先校準鍋爐座標。")
            return

        hwnd = self._get_hwnd()
        if not hwnd: return
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}")
            return

        sg      = max(game_w / MOLE_W, game_h / MOLE_H)
        img_rgb = img.convert("RGB")

        CALIB_HINTS = {
            "clock_offset":   "請在右側放大圖中，點擊橙色時鐘圓圈的中心位置",
            "done_offset":    "請在右側放大圖中，點擊黃色光暈最亮的位置",
            "spoiled_offset": "請在右側放大圖中，點擊鍋爐上方黑色煙霧的位置",
        }
        pt_hint = CALIB_HINTS.get(offset_key, f"請在右側放大圖中，點擊「{label}」對應位置")

        LEFT_MAX_W, LEFT_MAX_H = 480, 400
        left_scale = min(LEFT_MAX_W / game_w, LEFT_MAX_H / game_h, 1.0)
        lw = int(game_w * left_scale)
        lh = int(game_h * left_scale)
        left_photo = ImageTk.PhotoImage(img.resize((lw, lh), Image.LANCZOS))

        ZOOM_R      = 60
        ZOOM_SIZE   = 320
        zoom_factor = ZOOM_SIZE / (ZOOM_R * 2)

        # ── 每個鍋爐的校準資料（None = 未校準） ──────────────
        c_pts = [None] * n   # [dx,dy,r,g,b]
        c_hsv = [None] * n   # hsv_cfg dict
        cur   = [0]          # 目前選中的鍋爐

        # 載入既有校準（方便只改特定鍋爐）
        ex_pts = self._extra_settings.get(points_key) or []
        ex_hsv = self._extra_settings.get(hsv_list_key) or []
        if len(ex_pts) == n:
            for i in range(n): c_pts[i] = list(ex_pts[i])
        if len(ex_hsv) == n:
            for i in range(n): c_hsv[i] = dict(ex_hsv[i])

        # ── 視窗 ─────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"校準「{label}」（各鍋爐獨立）")
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win, text="點擊上方鍋爐按鈕切換，在放大圖或全景點擊校準",
                  font=("", 11, "bold"), padding=(8, 8, 8, 2)).pack()
        ttk.Label(win, text=pt_hint + "　（放大圖找不到時直接點左側全景）",
                  foreground="gray", padding=(8, 0, 8, 4), wraplength=820).pack()

        # ── 頂部鍋爐切換按鈕列 ───────────────────────────────
        sel_row = ttk.Frame(win)
        sel_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Label(sel_row, text="切換鍋爐：").pack(side=tk.LEFT)
        stove_btns = []
        for i in range(n):
            b = tk.Button(sel_row, text=f"爐{i+1}  ——", width=10,
                          font=("", 9), relief=tk.RAISED,
                          command=lambda idx=i: select_stove(idx))
            b.pack(side=tk.LEFT, padx=2)
            stove_btns.append(b)

        # ── 雙面板 ───────────────────────────────────────────
        panels = ttk.Frame(win)
        panels.pack(padx=8, pady=4)

        lf = ttk.LabelFrame(panels, text="全景（點鍋爐圓圈切換，或直接點擊校準）")
        lf.pack(side=tk.LEFT, padx=(0, 8), anchor=tk.N)
        left_canvas = tk.Canvas(lf, width=lw, height=lh, cursor="crosshair")
        left_canvas.pack()
        left_canvas.create_image(0, 0, anchor=tk.NW, image=left_photo)
        left_canvas.photo = left_photo

        rf = ttk.LabelFrame(panels, text="放大圖（在此點擊校準）")
        rf.pack(side=tk.LEFT, anchor=tk.N)
        zoom_canvas = tk.Canvas(rf, width=ZOOM_SIZE, height=ZOOM_SIZE,
                                cursor="crosshair", bg="#1a1a1a")
        zoom_canvas.pack()
        pct_lbl = ttk.Label(rf, text="請先選擇要校準的鍋爐", foreground="gray",
                             padding=(4, 2), font=("", 9), wraplength=ZOOM_SIZE)
        pct_lbl.pack()

        stove_ovals = []
        for i, (sx2, sy2) in enumerate(self.stoves):
            ex = int(sx2 * sg * left_scale)
            ey = int(sy2 * sg * left_scale)
            ov = left_canvas.create_oval(ex-12, ey-12, ex+12, ey+12,
                                         outline="gray", width=2)
            tx = left_canvas.create_text(ex, ey, text=str(i+1),
                                         fill="gray", font=("Arial", 9, "bold"))
            stove_ovals.append((ov, tx))

        zoom_photo_ref = [None]

        # ── 計算第 i 爐匹配率 ────────────────────────────────
        def calc_pct(i):
            h = c_hsv[i]; p = c_pts[i]
            if not h or not p: return None
            sx2, sy2 = self.stoves[i]
            return _hsv_match_pct(img_rgb, sg, sx2 + h["cx"], sy2 + h["cy"],
                                   h["radius"], h["h"], h["s"], h["v"])

        def update_stove_btn(i):
            pct = calc_pct(i)
            if pct is None:
                txt, fg, bg = f"爐{i+1}  ——", "gray", "SystemButtonFace"
            else:
                thr  = c_hsv[i].get("pct", 0.12)
                mark = "✓" if pct >= thr else "⚠"
                txt  = f"爐{i+1} {pct*100:.0f}%{mark}"
                fg   = "#1a7a1a" if pct >= thr else "#8a4a00"
                bg   = "#d4f5d4" if pct >= thr else "#fff0c0"
            stove_btns[i].config(text=txt, fg=fg, bg=bg,
                                 relief=tk.SUNKEN if i == cur[0] else tk.RAISED)

        def update_left_markers():
            for i, (ov, tx) in enumerate(stove_ovals):
                pct = calc_pct(i)
                if i == cur[0]:
                    col, ww = "#00dd00", 3
                elif pct is None:
                    col, ww = "gray", 2
                else:
                    thr = c_hsv[i].get("pct", 0.12)
                    col = "#27ae60" if pct >= thr else "orange"
                    ww  = 2
                left_canvas.itemconfig(ov, outline=col, width=ww)
                left_canvas.itemconfig(tx, fill=col)

        def show_zoom(i, dot_mx=None, dot_my=None):
            sx2, sy2 = self.stoves[i]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            px0 = min(max(int(mx0 * sg), 0), game_w)
            py0 = min(max(int(my0 * sg), 0), game_h)
            px1 = min(int((mx0 + ZOOM_R * 2) * sg), game_w)
            py1 = min(int((my0 + ZOOM_R * 2) * sg), game_h)
            z = img_rgb.crop((px0, py0, px1, py1)).resize(
                    (ZOOM_SIZE, ZOOM_SIZE), Image.LANCZOS)
            from PIL import ImageDraw
            draw = ImageDraw.Draw(z)
            cx_c = int((sx2 - mx0) * zoom_factor)
            cy_c = int((sy2 - my0) * zoom_factor)
            draw.line([(cx_c-14, cy_c), (cx_c+14, cy_c)], fill="#ffffff", width=1)
            draw.line([(cx_c, cy_c-14), (cx_c, cy_c+14)], fill="#ffffff", width=1)
            if dot_mx is not None:
                dx_c = int((dot_mx - mx0) * zoom_factor)
                dy_c = int((dot_my - my0) * zoom_factor)
                draw.ellipse([dx_c-9, dy_c-9, dx_c+9, dy_c+9], outline="red", width=3)
                draw.line([(dx_c-14, dy_c), (dx_c+14, dy_c)], fill="red", width=2)
                draw.line([(dx_c, dy_c-14), (dx_c, dy_c+14)], fill="red", width=2)
            photo = ImageTk.PhotoImage(z)
            zoom_canvas.delete("all")
            zoom_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            zoom_canvas.photo = photo
            zoom_photo_ref[0] = photo

        def show_pct(i, rgb=None):
            """更新右側下方的匹配率 + 顏色說明"""
            pct = calc_pct(i)
            if pct is None:
                pct_lbl.config(text=f"鍋爐 {i+1}：尚未校準，請點放大圖",
                               foreground="gray"); return
            thr    = c_hsv[i].get("pct", 0.12)
            status = "✓ 正常" if pct >= thr else "⚠ 偏低，建議重點"
            # 顏色說明
            src = rgb if rgb else (c_pts[i][2:5] if c_pts[i] else None)
            if src:
                hh, ss, vv = _rgb_to_hsv(*src)
                cname = _hsv_color_name(hh, ss, vv)
                hcfg  = _STATE_COLOR_HINTS.get(offset_key)
                if hcfg:
                    ok    = hcfg["check"](hh, ss, vv)
                    cline = (f"{'✓' if ok else '⚠'} 顏色：{cname}"
                             + ("" if ok else f"（應為{hcfg['expect']}）"))
                    cfg   = "#27ae60" if ok else "orange"
                else:
                    cline = f"顏色：{cname}"; cfg = "gray"
            else:
                cline = ""; cfg = "#27ae60" if pct >= thr else "orange"
            pct_lbl.config(
                text=(f"鍋爐 {i+1}：匹配率 {pct*100:.0f}%（閾值 {thr*100:.0f}%）{status}"
                      + (f"\n{cline}" if cline else "")),
                foreground=cfg)

        def select_stove(i):
            cur[0] = i
            show_zoom(i)
            show_pct(i)
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        for i in range(n): update_stove_btn(i)
        select_stove(0)

        def _do_pick(click_mx, click_my):
            i = cur[0]
            sx2, sy2 = self.stoves[i]
            click_px = min(max(int(click_mx * sg), 0), game_w - 1)
            click_py = min(max(int(click_my * sg), 0), game_h - 1)
            rgb = img_rgb.getpixel((click_px, click_py))
            dx  = round(click_mx - sx2); dy = round(click_my - sy2)
            c_pts[i] = [dx, dy, rgb[0], rgb[1], rgb[2]]
            hsv_cfg  = _sample_hsv_range(img_rgb, click_px, click_py, sample_r=5)
            hsv_cfg["cx"] = dx; hsv_cfg["cy"] = dy
            c_hsv[i] = hsv_cfg
            show_zoom(i, click_mx, click_my)
            show_pct(i, rgb)
            for j in range(n): update_stove_btn(j)
            update_left_markers()

            # 顏色不對時不自動跳下一爐，讓使用者看到警告後重新點擊
            hcfg = _STATE_COLOR_HINTS.get(offset_key)
            if hcfg:
                hh, ss, vv = _rgb_to_hsv(*rgb)
                if not hcfg["check"](hh, ss, vv):
                    return   # 顏色警告已顯示在下方，停在這爐等重點

            # 顏色正確，0.8s 後自動跳到下一個尚未校準的鍋爐
            def auto_next():
                for j in range(1, n + 1):
                    nxt = (i + j) % n
                    if c_pts[nxt] is None:
                        select_stove(nxt); return
                pct_lbl.config(text=f"全部 {n} 個鍋爐已校準！確認後按儲存。",
                               foreground="#27ae60")
            win.after(800, auto_next)

        def on_zoom_click(event):
            sx2, sy2 = self.stoves[cur[0]]
            mx0 = sx2 - ZOOM_R; my0 = sy2 - ZOOM_R
            _do_pick(mx0 + event.x / zoom_factor, my0 + event.y / zoom_factor)

        def on_left_click(event):
            click_mx = (event.x / left_scale) / sg
            click_my = (event.y / left_scale) / sg
            # 點在鍋爐圓圈附近 → 切換目標
            for i, (sx2, sy2) in enumerate(self.stoves):
                if ((click_mx - sx2)**2 + (click_my - sy2)**2) ** 0.5 < 20:
                    select_stove(i); return
            _do_pick(click_mx, click_my)

        def on_clear_one():
            i = cur[0]
            c_pts[i] = None; c_hsv[i] = None
            show_zoom(i)
            pct_lbl.config(text=f"鍋爐 {i+1} 已清除，請重新校準", foreground="gray")
            for j in range(n): update_stove_btn(j)
            update_left_markers()

        def on_clear_all():
            for i in range(n): c_pts[i] = None; c_hsv[i] = None
            for k in (points_key, hsv_list_key):
                self._extra_settings[k] = []; self.bot.settings[k] = []
            if not self._save_all():
                return
            pct_lbl.config(text="已清空所有校準點", foreground="gray")
            for j in range(n): update_stove_btn(j)
            select_stove(cur[0])

        def on_save():
            missing = [i+1 for i in range(n) if c_pts[i] is None]
            if missing:
                messagebox.showwarning("提示", f"鍋爐 {missing} 尚未校準。"); return
            self._extra_settings[points_key]   = list(c_pts)
            self._extra_settings[hsv_list_key] = list(c_hsv)
            self.bot.settings[points_key]      = list(c_pts)
            self.bot.settings[hsv_list_key]    = list(c_hsv)
            for k in (color_key, offset_key):
                if k:
                    self._extra_settings[k] = None; self.bot.settings[k] = None
            if not self._save_all():
                return
            self._refresh_calib_status()
            win.destroy()
            messagebox.showinfo("完成", f"「{label}」已儲存 {n} 個獨立校準點（含 HSV 區域偵測）。")

        zoom_canvas.bind("<Button-1>", on_zoom_click)
        left_canvas.bind("<Button-1>", on_left_click)

        nav_frame = ttk.Frame(win)
        nav_frame.pack(pady=(4, 0))
        ttk.Button(nav_frame, text="◀ 上一爐",
                   command=lambda: select_stove((cur[0] - 1) % n)).pack(side=tk.LEFT, padx=8)
        ttk.Button(nav_frame, text="下一爐 ▶",
                   command=lambda: select_stove((cur[0] + 1) % n)).pack(side=tk.LEFT, padx=8)

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)
        ttk.Button(btn_frame, text="儲存",     command=on_save     ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除此爐", command=on_clear_one).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除全部", command=on_clear_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消",     command=win.destroy ).pack(side=tk.LEFT, padx=6)

    def _calib_stoves(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        prompts = [f"第 {i+1} 個鍋爐" for i in range(6)]
        CalibrationWindow(self.root, hwnd, prompts, self._done_stoves)

    def _done_stoves(self, pts):
        self.stoves = pts
        self.bot.stoves = pts
        if not self._save_all():
            return
        self._refresh_calib_status()
        messagebox.showinfo("完成", "鍋爐座標已儲存！")

    def _calib_recipe(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        prompts = (
            ["左箭頭 (←)", "右箭頭 (→)", "關閉按鈕 (X)"] +
            [f"頁碼 Tab {i+1}" for i in range(5)] +
            [f"菜格 {i+1}" for i in range(6)] +
            ["食譜中心偵測點（點食譜空白處任意一點）"]
        )
        messagebox.showinfo(
            "校準食譜",
            "請先手動點鍋爐打開食譜，再來這裡截圖校準。\n\n"
            "依序點擊：左箭頭、右箭頭、關閉按鈕(X)、\n"
            "頁碼Tab 1~5、菜格 1~6（左到右、上到下）、\n"
            "最後點食譜內任意空白處作為偵測點",
        )
        CalibrationWindow(self.root, hwnd, prompts, self._done_recipe)

    def _done_recipe(self, pts):
        # 保留已校準的 confirm_btn / cancel_btn，不因重新校準食譜而被清除
        self.recipe = {
            "left_arrow":  pts[0],
            "right_arrow": pts[1],
            "close":       pts[2],
            "page_tabs":   pts[3:8],
            "dishes":      pts[8:14],
            "check_pt":    pts[14],
            "confirm_btn": self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"]),
            "cancel_btn":  self.recipe.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"]),
        }
        self.bot.recipe = self.recipe
        if not self._save_all():
            return
        self._refresh_calib_status()
        messagebox.showinfo("完成", "食譜座標已儲存！")

    def _test_navigate(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        self.bot.hwnd = hwnd
        self.bot._stop.clear()
        page = self.vars["page"].get()
        self._on_status(f"測試換頁：目標第 {page} 頁（請先手動開食譜）")
        def _run():
            self.bot.navigate_to_page(page)
            self._on_status(f"換頁完成，請確認遊戲目前是否在第 {page} 頁")
        threading.Thread(target=_run, daemon=True).start()

    def _take_live_snap(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        self.bot.hwnd = hwnd
        self.bot.save_live_snapshot("手動截圖")
        self._on_status(f"截圖已存到 tools/debug/bot_live.png")

    def _open_detect_test(self):
        """
        即時偵測測試視窗：每 0.5 秒掃一次所有鍋爐，
        顯示偵測到的狀態及各項目的色差 Δ 值，幫助確認校準是否正確。
        """
        hwnd = self._get_hwnd()
        if not hwnd: return
        self.bot.hwnd = hwnd

        win = tk.Toplevel(self.root)
        win.title("偵測測試（即時）")
        win.resizable(False, False)

        ttk.Label(win,
                  text="每 0.2 秒掃一次。HSV 模式顯示匹配率（% 越高越命中），RGB 模式顯示色差 Δ（越小越命中）。",
                  padding=(10, 8, 10, 4), wraplength=520).pack()

        threshold = self.bot.settings.get("state_threshold", 40)
        ttk.Label(win, text=f"RGB threshold = {threshold}  ｜  HSV 預設閾值 = 12%",
                  foreground="gray", padding=(10, 0, 10, 6)).pack()

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill=tk.BOTH)

        # 表頭
        headers = ["鍋爐", "座標", "狀態", "做完", "時鐘"]
        for col, h in enumerate(headers):
            ttk.Label(frame, text=h, font=("", 9, "bold"),
                      padding=(6, 2)).grid(row=0, column=col, sticky=tk.W)

        # 每個鍋爐一行標籤
        row_labels = []
        for i in range(len(self.stoves)):
            cols = []
            for col in range(len(headers)):
                lbl = ttk.Label(frame, text="—", padding=(6, 1))
                lbl.grid(row=i+1, column=col, sticky=tk.W)
                cols.append(lbl)
            row_labels.append(cols)

        stop_event = threading.Event()

        def refresh_loop():
            """
            整個迴圈留在背景執行緒，UI 更新用 win.after(0, ...) 拋回主執行緒。
            每輪只截一張圖，所有鍋爐共用，避免重複截圖造成卡頓。
            """
            while not stop_event.is_set():
                if not win.winfo_exists():
                    break

                s         = self.bot.settings
                threshold = s.get("state_threshold", 40)

                # 截一張圖供本輪所有鍋爐共用
                try:
                    raw_img, gw, gh = capture_window(self.bot.hwnd)
                    img   = raw_img.convert("RGB")
                    scale = max(gw / MOLE_W, gh / MOLE_H)
                except Exception:
                    time.sleep(1.0)
                    continue

                def get_px(mx, my):
                    px = min(max(int(mx * scale), 0), gw - 1)
                    py = min(max(int(my * scale), 0), gh - 1)
                    return img.getpixel((px, py))

                def hsv_score(hsv_list_key, _sx, _sy, _idx):
                    """HSV 模式：回傳 'XX% ✓' 或 'XX%' 或 None（未設定）"""
                    hsv_list = s.get(hsv_list_key) or []
                    if not hsv_list or _idx >= len(hsv_list):
                        return None
                    cfg = hsv_list[_idx]
                    if not cfg:
                        return None
                    cx = _sx + cfg.get("cx", 0)
                    cy = _sy + cfg.get("cy", 0)
                    pct = _hsv_match_pct(img, scale, cx, cy,
                                         cfg.get("radius", 10),
                                         cfg.get("h", [0, 360]),
                                         cfg.get("s", [0, 100]),
                                         cfg.get("v", [0, 100]))
                    pct_thr = cfg.get("pct", 0.12)
                    mark = " ✓" if pct >= pct_thr else ""
                    return f"{pct*100:.0f}%{mark}"

                def best_delta(pts_key, color_key, off_key, spread, _sx, _sy, _idx):
                    """RGB 模式：回傳 'Δ ✓' 或 'Δ' 或 '未校準'"""
                    pts   = s.get(pts_key) or []
                    color = s.get(color_key)
                    off   = s.get(off_key) or [0, 0]
                    if not pts and not color:
                        return "未校準"
                    best = 999
                    if pts:
                        if len(pts) == len(self.bot.stoves):
                            relevant = [pts[_idx]] if _idx < len(pts) else pts
                        else:
                            relevant = pts
                        entries = [(e[0], e[1], (e[2], e[3], e[4])) for e in relevant]
                    else:
                        entries = [(off[0], off[1], tuple(color))]
                    for dx, dy, ref in entries:
                        mx, my = _sx + dx, _sy + dy
                        for ddx, ddy in ((0,0),(spread,0),(-spread,0),(0,spread),(0,-spread)):
                            d = self.bot.color_diff(get_px(mx+ddx, my+ddy), ref)
                            if d < best:
                                best = d
                    mark = " ✓" if best < threshold else ""
                    return f"{best}{mark}"

                def state_score(hsv_key, pts_key, col_key, off_key, spread, _sx, _sy, _idx):
                    """優先用 HSV，若無才用 RGB"""
                    hs = hsv_score(hsv_key, _sx, _sy, _idx)
                    if hs is not None:
                        return hs, hs
                    bd = best_delta(pts_key, col_key, off_key, spread, _sx, _sy, _idx)
                    return bd, bd

                def parse_score(txt):
                    """從顯示文字推算命中分數（用於狀態推斷）"""
                    if "未校準" in txt:
                        return 999, False
                    hit = "✓" in txt
                    try:
                        num = float(txt.replace("%", "").replace("✓", "").strip())
                        # HSV%：命中判斷看 ✓；RGB Δ：命中判斷看 ✓
                        return num, hit
                    except ValueError:
                        return 999, False

                for i, (sx, sy) in enumerate(self.bot.stoves):
                    if stop_event.is_set():
                        break

                    done_txt,  _ = state_score("done_hsv_list",  "done_points",  "done_color",  "done_offset",  4, sx, sy, i)
                    clock_txt, _ = state_score("clock_hsv_list", "clock_points", "clock_color", "clock_offset", 4, sx, sy, i)

                    _, done_hit  = parse_score(done_txt)
                    _, clock_hit = parse_score(clock_txt)

                    if done_hit:
                        state = "done"
                    elif clock_hit:
                        state = "cooking"
                    else:
                        state = "unknown"

                    sc = {"cooking": "blue", "done": "orange",
                          "unknown": "gray"}.get(state, "gray")

                    def update_row(idx=i, st=state, fg=sc,
                                   dd=done_txt, cd=clock_txt):
                        if not win.winfo_exists():
                            return
                        row_labels[idx][0].config(text=str(idx+1))
                        row_labels[idx][1].config(text=str(self.bot.stoves[idx]))
                        row_labels[idx][2].config(text=st, foreground=fg)
                        row_labels[idx][3].config(text=dd)
                        row_labels[idx][4].config(text=cd)

                    win.after(0, update_row)

                time.sleep(0.2)   # 快速刷新，讓動畫造成的 Δ 變化即時可見

        def on_close():
            stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        threading.Thread(target=refresh_loop, daemon=True).start()

    def _on_status(self, msg, error=False):
        color = "red" if error else ("gray" if msg == "已停止" else "green")
        self.root.after(0, lambda: self.status.config(text=f"狀態：{msg}", foreground=color))
        if msg == "已停止" or error:
            self.root.after(0, lambda: self._set_running(False))
        if error:
            self.root.after(0, lambda: messagebox.showerror("錯誤", msg))


def _check_ocr_language():
    """檢查 Windows 是否已安裝中文 OCR 語言包。
    若未安裝，顯示一次性提示說明如何安裝，但不阻止程式啟動。"""
    try:
        import winsdk.windows.media.ocr as ocr
        import winsdk.windows.globalization as glob
        for tag in ["zh-Hans-CN", "zh-TW"]:
            if ocr.OcrEngine.is_language_supported(glob.Language(tag)):
                return  # 有支援，不需提示
        # 都不支援
        messagebox.showwarning(
            "OCR 語言包未安裝",
            "目前 Windows 未安裝中文 OCR 語言包，\n"
            "彈窗偵測（燒糊 / 捐菜）將無法使用，\n"
            "機器人仍可運作，但彈窗處理會改用保守策略。\n\n"
            "如需啟用 OCR，請依照以下步驟安裝：\n"
            "1. 開啟「設定」→「時間與語言」→「語言」\n"
            "2. 新增「中文（簡體，中國）」或「中文（繁體，台灣）」\n"
            "3. 點「選項」，確認「光學字元辨識」已勾選下載\n"
            "4. 下載完成後重新啟動本程式"
        )
    except ImportError:
        messagebox.showwarning(
            "OCR 套件未安裝",
            "找不到 winsdk 套件，彈窗文字偵測無法使用。\n"
            "機器人仍可運作，但彈窗處理會改用保守策略。\n\n"
            "（此訊息通常不應出現，請聯絡提供程式的人）"
        )
    except Exception:
        pass


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.after(500, _check_ocr_language)   # 視窗開好後再顯示，避免被主視窗蓋住
    root.mainloop()

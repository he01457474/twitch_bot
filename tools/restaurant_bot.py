import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
import ctypes
import win32gui
import win32api
import win32ui
import win32con
from PIL import Image, ImageTk

# 隱藏 CMD 視窗
try:
    hwnd_con = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd_con:
        ctypes.windll.user32.ShowWindow(hwnd_con, 0)
except Exception:
    pass

MOLE_W = 960
MOLE_H = 560
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "restaurant_config.json")

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
}
MAP_BTN        = (33,  505)
HOME_BTN       = (880, 538)
RESTAURANT_BTN = (880, 449)


# ── 設定讀寫 ──────────────────────────────────────────

def load_config():
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
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
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"stoves": stoves, "recipe": recipe, "settings": settings}, f, indent=2)
    except Exception:
        pass


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

DEBUG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug")

class RestaurantBot:
    def __init__(self, stoves, recipe, settings):
        self.hwnd     = None
        self._stop    = threading.Event()
        self.stoves   = stoves
        self.recipe   = recipe
        self.settings = settings
        self._recipe_closed_baseline = None   # 食譜關閉時的 check_pt 顏色基準
        self._debug   = False                 # Debug 模式：存標記截圖

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

    def detect_stove_state(self, sx, sy):
        """
        比對鍋爐狀態，回傳 "done" / "cooking" / "spoiled" / "unknown"。

        優先使用多點格式（done_points / clock_points / spoiled_points），
        每個校準點格式為 [dx, dy, r, g, b]，任一符合即視為偵測到該狀態。
        若多點列表為空，則 fallback 至舊的單點格式（*_color + *_offset）。

        每個校準點還會在周邊十字取樣 5 個點取最小色差，
        對 NPC 對話框或坐騎遮擋一部分時有更強的容錯。
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

        def check_state(points_key, old_color_key, old_offset_key, spread=4):
            """
            先檢查多點清單，再 fallback 舊格式。
            回傳 (偵測到: bool, 最佳 Δ: int, 第一個點的 mole 座標 for debug)
            """
            points = self.settings.get(points_key) or []
            if points:
                best_overall = 999
                first_xy = (sx + points[0][0], sy + points[0][1])
                for entry in points:
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

        # done 優先（黃光蓋在時鐘上面）
        hit, diff, (dx, dy) = check_state("done_points", "done_color", "done_offset")
        markers.append((dx, dy, "yellow", f"done Δ{diff}"))
        if hit:
            self._debug_capture(f"done_{sx}_{sy}", markers)
            return "done"

        # 時鐘 → 烹飪中
        hit, diff, (cx, cy) = check_state("clock_points", "clock_color", "clock_offset")
        markers.append((cx, cy, "orange", f"clock Δ{diff}"))
        if hit:
            return "cooking"

        # 腐壞黑煙（spread 較大，煙會漂移）
        hit, diff, (spx, spy) = check_state("spoiled_points", "spoiled_color", "spoiled_offset", spread=6)
        markers.append((spx, spy, "red", f"spoiled Δ{diff}"))
        if hit:
            self._debug_capture(f"spoiled_{sx}_{sy}", markers)
            return "spoiled"

        return "unknown"

    def is_stove_spoiled(self, sx, sy):
        return self.detect_stove_state(sx, sy) == "spoiled"

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
        return self.color_diff(current, tuple(color)) < threshold

    def is_recipe_open(self):
        """根據 check_pt 和記錄的關閉基準色，判斷食譜是否開著"""
        if self._recipe_closed_baseline is None:
            return False
        current = self.get_pixel(*self.recipe["check_pt"])
        threshold = self.settings.get("state_threshold", 40)
        return self.color_diff(current, tuple(self._recipe_closed_baseline)) > threshold

    def _complete_to_cooking(self, sx, sy, log, max_steps=3, start_step=1):
        """
        從 start_step 繼續點擊直到進入烹飪狀態。
        每步點完立即確認讀條出現；若無反應回傳 False。
        """
        step_labels = {1: "製作餐具", 2: "放入食材", 3: "開始烹飪"}
        for i in range(max_steps):
            if self._stop.is_set(): return True
            # 每步前先確認狀態
            state = self.detect_stove_state(sx, sy)
            if state in ("cooking", "done"):
                log(f"鍋爐 ({sx},{sy}) 已烹飪 ✓")
                return True
            if state == "spoiled":
                log("偵測到腐壞，停止接續步驟")
                return False
            label = step_labels.get(start_step + i, f"步驟 {start_step + i}")
            log(f"{label}…")
            pre = self.get_pixel(sx, sy)
            self.click(sx, sy, delay=0.1)
            # 點完馬上確認有沒有讀條（1 秒內）
            ok, _, bar_color = self.wait_for_pixel_change(sx, sy, timeout=1.0, baseline=pre)
            if not ok:
                if self.detect_stove_state(sx, sy) in ("cooking", "done"):
                    log(f"鍋爐 ({sx},{sy}) 已烹飪 ✓")
                    return True
                log(f"{label}：點擊無反應")
                self._debug_capture(f"no_bar_{sx}_{sy}_step{start_step+i}")
                return False
            # 讀條出現，先排除腐壞提示（腐壞時點擊也會有短暫像素變化）
            if self.detect_stove_state(sx, sy) == "spoiled":
                log("偵測到腐壞提示（非製作讀條），停止接續步驟")
                return False
            log(f"{label}：讀條中…")
            # 等讀條結束，同時監控烹飪狀態 — 一出現時鐘就立刻離開
            deadline = time.time() + 15.0
            while time.time() < deadline and not self._stop.is_set():
                st = self.detect_stove_state(sx, sy)
                if st in ("cooking", "done"):
                    log(f"鍋爐 ({sx},{sy}) 已烹飪 ✓")
                    return True
                if self.color_diff(self.get_pixel(sx, sy), bar_color) > 40:
                    break  # 讀條結束
                time.sleep(0.2)
            time.sleep(0.3)
        # 所有步驟跑完，最後確認
        if self.detect_stove_state(sx, sy) in ("cooking", "done"):
            log(f"鍋爐 ({sx},{sy}) 已烹飪 ✓")
        return True

    def find_window(self):
        found = []
        def cb(hwnd, _):
            if "Adobe Flash Player" in win32gui.GetWindowText(hwnd) and win32gui.IsWindowVisible(hwnd):
                found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

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
            time.sleep(delay)

    def click_real(self, mole_x, mole_y, delay=0.1):
        """移動游標到位置後 SendMessage（不搶視窗焦點，但游標會移動）"""
        if not self.hwnd:
            return
        rect  = win32gui.GetClientRect(self.hwnd)
        w, h  = rect[2], rect[3]
        scale = max(w / MOLE_W, h / MOLE_H)
        cx, cy = int(mole_x * scale), int(mole_y * scale)
        lp = (cy << 16) | (cx & 0xFFFF)
        try:
            # 用 GetWindowRect 算螢幕位置，避免 DPI 縮放問題
            wr = win32gui.GetWindowRect(self.hwnd)
            cr = win32gui.GetClientRect(self.hwnd)
            # client area 相對於 window 的偏移 = (wr.right-wr.left-cr.right)//2 為邊框寬
            border_x = (wr[2] - wr[0] - cr[2]) // 2
            border_y = (wr[3] - wr[1] - cr[3]) - border_x
            sx = wr[0] + border_x + cx
            sy = wr[1] + border_y + cy
            win32api.SetCursorPos((sx, sy))
            time.sleep(0.05)
        except Exception:
            pass
        win32api.SendMessage(self.hwnd, 0x201, 1, lp)
        win32api.SendMessage(self.hwnd, 0x202, 0, lp)
        if delay > 0:
            time.sleep(delay)

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
            on_status("防卡頓：前往地圖…")
            self.click(*MAP_BTN, delay=3.0)
            if self._stop.is_set(): return
            on_status("防卡頓：回到餐廳…")
            self.click(*HOME_BTN, delay=1.0)
            self.click(*RESTAURANT_BTN, delay=3.0)

    def wait_with_antlag(self, total_seconds, interval_seconds, on_status, msg):
        elapsed = 0.0
        since_antlag = 0.0   # 距上次防卡頓已過幾秒
        while elapsed < total_seconds and not self._stop.is_set():
            rem = total_seconds - elapsed
            on_status(f"{msg}（剩餘 {int(rem//60)} 分 {int(rem%60)} 秒）")
            # 每秒一格，0.1s 檢查一次 stop
            for _ in range(10):
                if self._stop.is_set():
                    return False
                time.sleep(0.1)
            elapsed     += 1.0
            since_antlag += 1.0
            # 到防卡頓間隔就出去繞一圈
            if since_antlag >= interval_seconds and elapsed < total_seconds:
                self.leave_and_return(on_status)
                if not self._is_in_restaurant():
                    on_status("防卡頓後未偵測到餐廳畫面，30 秒後重試…")
                    since_antlag = interval_seconds - 30  # 30 秒後再試一次
                else:
                    since_antlag = 0.0
        return not self._stop.is_set()

    def navigate_to_page(self, target_page):
        r = self.recipe
        # 先連按左箭頭確保回到第 1 頁
        for _ in range(15):
            if self._stop.is_set(): return
            self.click_real(*r["left_arrow"], delay=0.15)

        # 右箭頭本身就會切換頁面，不需要額外點 tab
        # 第 1 頁 = 0 次，第 2 頁 = 1 次，依此類推
        for _ in range(target_page - 1):
            if self._stop.is_set(): return
            self.click_real(*r["right_arrow"], delay=0.15)

        time.sleep(0.3)

    def _select_dish(self, page, dish, check, log):
        """換頁 + 點菜色 + 等食譜關閉。成功回傳 True。"""
        log(f"切換到第 {page} 頁…")
        self.navigate_to_page(page)
        if self._stop.is_set(): return False

        dish_pt = self.recipe["dishes"][dish - 1]
        log(f"點菜色 {dish}…")
        pre = self.get_pixel(*check)
        self.click_real(*dish_pt, delay=0.3)
        ok, _, _ = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)
        if not ok:
            log("點菜後食譜沒有關閉，請重新校準菜格座標")
            return False
        log("食譜已關閉 ✓")
        # 食譜剛關閉，順便更新基準色（最準確的時機）
        self._recipe_closed_baseline = list(self.get_pixel(*check))
        return True

    def setup_stove(self, sx, sy, page, dish, on_status=None):
        def log(msg):
            if on_status: on_status(msg)

        confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        cancel_btn  = self.recipe.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"])
        check       = self.recipe["check_pt"]
        threshold   = self.settings.get("state_threshold", 40)

        # ── 顏色預判：直接跳到對應步驟 ──────────────
        state = self.detect_stove_state(sx, sy)
        log(f"鍋爐 ({sx},{sy}) 狀態：{state}")

        if state == "cooking":
            log("烹飪中，跳過")
            return

        if state == "done":
            log("食物做好，收菜…")
            self.click(sx, sy, delay=1.0)
            time.sleep(1.5)
            # 收完後繼續往下重新下菜

        if state == "spoiled":
            for _try in range(2):   # 最多嘗試清除兩次
                log("腐壞，清除…")
                self.click(sx, sy, delay=0.5)   # 等彈窗完全出現
                time.sleep(0.8)
                self.click_real(*confirm_btn, delay=1.5)
                if self._stop.is_set(): return
                time.sleep(1.0)
                if self.detect_stove_state(sx, sy) != "spoiled":
                    break   # 清除成功
                log("清除後仍偵測到腐壞，再試一次…")
            # 清除後繼續往下重新下菜

        # ── 食譜是否已開著（例如使用者手動開了，或上輪未關） ──
        if self.is_recipe_open():
            log("食譜已開著，直接選菜…")
            if not self._select_dish(page, dish, check, log): return
            if self._stop.is_set(): return
            time.sleep(1.0)
            if not self._complete_to_cooking(sx, sy, log, max_steps=3):
                self._debug_capture(f"anomaly_{sx}_{sy}")
                log("步驟異常，返回鍋爐頁…")
                self.leave_and_return(log)
            return

        # ── 行為偵測：點鍋爐，觀察反應 ───────────────
        for attempt in range(3):
            if self._stop.is_set(): return

            pre_check = self.get_pixel(*check)
            pre_stove = self.get_pixel(sx, sy)
            self.click(sx, sy, delay=0.3)

            # 食譜開了？（先判斷，timeout 短一點）
            ok, _, _ = self.wait_for_pixel_change(*check, timeout=1.5, baseline=pre_check)
            if ok:
                log("食譜已開啟 ✓")
                if not self._select_dish(page, dish, check, log): return
                if self._stop.is_set(): return
                time.sleep(1.0)
                if not self._complete_to_cooking(sx, sy, log, max_steps=3):
                    log("步驟異常，返回鍋爐頁…")
                    self.leave_and_return(log)
                return

            # 讀條出現？（已在餐具或放入食材的中間步驟）
            stove_now = self.get_pixel(sx, sy)
            if self.color_diff(stove_now, pre_stove) > threshold:
                # 等 0.4 秒確認是持續讀條（腐壞提示是短暫的，真實讀條會持續幾秒）
                time.sleep(0.4)
                stove_persist = self.get_pixel(sx, sy)
                if self.color_diff(stove_persist, pre_stove) < threshold:
                    # 變化已消失 → 是短暫提示（腐壞 or 其他），不是真實讀條
                    if self.is_stove_spoiled(sx, sy):
                        log("腐壞，清除…")
                        self.click_real(*confirm_btn, delay=1.0)
                        time.sleep(0.5)
                    continue
                log("偵測到讀條（中間步驟），等待完成再接續…")
                self.wait_for_pixel_change(sx, sy, timeout=15.0, baseline=stove_now)
                time.sleep(0.5)
                if self.detect_stove_state(sx, sy) in ("cooking", "done"):
                    log(f"鍋爐 ({sx},{sy}) 已烹飪 ✓")
                    return
                # 讀條結束但還沒烹飪，接續剩餘步驟
                if not self._complete_to_cooking(sx, sy, log, max_steps=2):
                    log("步驟異常，返回鍋爐頁…")
                    self.leave_and_return(log)
                return

            # 都沒變 → 可能是彈窗
            if self.is_stove_spoiled(sx, sy):
                log("腐壞彈窗，清除…")
                self.click_real(*confirm_btn, delay=1.0)
            else:
                log("做菜中彈窗，取消，跳過")
                self.click_real(*cancel_btn, delay=0.5)
                return

        # 3 次都無反應 → 可能跳到奇怪的頁面，導航回來
        self._debug_capture(f"no_response_{sx}_{sy}")
        log(f"鍋爐 ({sx},{sy}) 持續無反應，返回鍋爐頁…")
        self.leave_and_return(log)

    def run(self, page, dish, scan_interval, antlag_minutes, on_status):
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗", error=True)
            return

        self._stop.clear()
        # 給 3 秒讓玩家確認食譜已關閉，再取基準色
        for i in range(3, 0, -1):
            if self._stop.is_set(): return
            on_status(f"請確認食譜已關閉，{i} 秒後開始…")
            self.wait(1)
        self._recipe_closed_baseline = list(self.get_pixel(*self.recipe["check_pt"]))
        # scan_interval 單位已是秒
        antlag_sec = antlag_minutes * 60 if antlag_minutes > 0 else scan_interval

        # 若未校準餐廳確認點，提醒但不阻擋
        if not self.settings.get("restaurant_pt") or not self.settings.get("restaurant_color"):
            on_status("提示：未校準餐廳確認點，建議校準以防止在餐廳外誤觸做菜")
            self.wait(3.0)

        while not self._stop.is_set():
            # 確認在餐廳內，否則嘗試導航回來
            if not self._is_in_restaurant():
                on_status("不在餐廳，嘗試返回…")
                self.leave_and_return(on_status)
                if self._stop.is_set(): break
                self.wait(2.0)
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
            for i, (sx, sy) in enumerate(self.stoves):
                if self._stop.is_set(): break
                on_status(f"【鍋爐 {i+1}/{n}】掃描中…")
                self.setup_stove(sx, sy, page, dish, on_status)
                on_status(f"【鍋爐 {i+1}/{n}】完成")
                if not self.wait(1.0): break

            if self._stop.is_set(): break

            # 等待下次掃描（含防卡頓）
            if not self.wait_with_antlag(scan_interval, antlag_sec, on_status, "等待掃描"): break

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
                       "state_threshold")
        self._extra_settings = {k: settings[k] for k in _extra_keys}
        self.bot = RestaurantBot(self.stoves, self.recipe, settings)
        self._build_ui(settings)

    def _build_ui(self, settings):
        f = ttk.Frame(self.root, padding=15)
        f.pack()

        self.vars = {}
        grid_row = 0

        # 一般單欄 spinbox 的欄位
        simple_rows = [
            ("食譜頁數 (1~10)",       "page",           1, 10),
            ("菜的位置 (1~6)",         "dish",           1,  6),
        ]
        for lbl, key, lo, hi in simple_rows:
            ttk.Label(f, text=lbl).grid(row=grid_row, column=0, sticky=tk.W, pady=4, padx=(0,8))
            v = tk.IntVar(value=settings[key])
            ttk.Spinbox(f, from_=lo, to=hi, textvariable=v, width=6).grid(
                row=grid_row, column=1, pady=4, sticky=tk.W)
            self.vars[key] = v
            grid_row += 1

        # 掃描間隔：分 + 秒合一行
        ttk.Label(f, text="掃描間隔").grid(row=grid_row, column=0, sticky=tk.W, pady=4, padx=(0,8))
        sf = ttk.Frame(f)
        sf.grid(row=grid_row, column=1, pady=4, sticky=tk.W)
        v_min = tk.IntVar(value=settings.get("cook_minutes", 20))
        v_sec = tk.IntVar(value=settings.get("cook_seconds", 0))
        ttk.Spinbox(sf, from_=0, to=99, textvariable=v_min, width=4).pack(side=tk.LEFT)
        ttk.Label(sf, text=" 分 ").pack(side=tk.LEFT)
        ttk.Spinbox(sf, from_=0, to=59, textvariable=v_sec, width=4).pack(side=tk.LEFT)
        ttk.Label(sf, text=" 秒").pack(side=tk.LEFT)
        self.vars["cook_minutes"] = v_min
        self.vars["cook_seconds"] = v_sec
        grid_row += 1

        # 防卡頓
        ttk.Label(f, text="防卡頓間隔（分，0=關）").grid(
            row=grid_row, column=0, sticky=tk.W, pady=4, padx=(0,8))
        v_al = tk.IntVar(value=settings.get("antlag_minutes", 5))
        ttk.Spinbox(f, from_=0, to=99, textvariable=v_al, width=6).grid(
            row=grid_row, column=1, pady=4, sticky=tk.W)
        self.vars["antlag_minutes"] = v_al
        grid_row += 1

        self.status = ttk.Label(f, text="狀態：待機", foreground="gray")
        self.status.grid(row=grid_row, column=0, columnspan=2, pady=(10, 4))
        grid_row += 1

        # 第一排：操作按鈕
        row_op = ttk.Frame(f)
        row_op.grid(row=grid_row, column=0, columnspan=2, pady=(0, 3))
        self.start_btn   = ttk.Button(row_op, text="開始",    command=self._start)
        self.stop_btn    = ttk.Button(row_op, text="停止",    command=self._stop, state=tk.DISABLED)
        self.testnav_btn = ttk.Button(row_op, text="測試換頁", command=self._test_navigate)
        self.testdet_btn = ttk.Button(row_op, text="偵測測試", command=self._open_detect_test)
        for btn in (self.start_btn, self.stop_btn, self.testnav_btn, self.testdet_btn):
            btn.pack(side=tk.LEFT, padx=4)
        grid_row += 1

        # 第二排：校準按鈕
        row_cal = ttk.Frame(f)
        row_cal.grid(row=grid_row, column=0, columnspan=2, pady=(0, 2))
        self.calib_s  = ttk.Button(row_cal, text="校準鍋爐",   command=self._calib_stoves)
        self.calib_r  = ttk.Button(row_cal, text="校準食譜",   command=self._calib_recipe)
        self.calib_c  = ttk.Button(row_cal, text="校準彈窗",   command=self._calib_cancel)
        self.calib_sp = ttk.Button(row_cal, text="校準狀態色", command=self._calib_state_colors)
        for btn in (self.calib_s, self.calib_r, self.calib_c, self.calib_sp):
            btn.pack(side=tk.LEFT, padx=4)
        grid_row += 1

        # 第三排：工具按鈕
        row_tool = ttk.Frame(f)
        row_tool.grid(row=grid_row, column=0, columnspan=2, pady=(0, 4))
        self.calib_door  = ttk.Button(row_tool, text="校準門口",  command=self._calib_door)
        self.calib_rest  = ttk.Button(row_tool, text="校準餐廳",  command=self._calib_restaurant)
        self.preview_btn = ttk.Button(row_tool, text="預覽座標",  command=self._preview_coords)
        self._debug_var  = tk.BooleanVar(value=False)
        self.debug_btn   = ttk.Checkbutton(row_tool, text="Debug 截圖",
                                           variable=self._debug_var,
                                           command=self._toggle_debug)
        for btn in (self.calib_door, self.calib_rest, self.preview_btn, self.debug_btn):
            btn.pack(side=tk.LEFT, padx=4)

    def _toggle_debug(self):
        on = self._debug_var.get()
        self.bot._debug = on
        if on:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            messagebox.showinfo("Debug 截圖", f"已開啟，截圖存到：\n{DEBUG_DIR}")
        else:
            messagebox.showinfo("Debug 截圖", "已關閉。")

    def _get_settings(self):
        s = {k: v.get() for k, v in self.vars.items()}
        s.update(self._extra_settings)  # 合併 spoiled_color / spoiled_threshold
        return s

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        for btn in (self.start_btn, self.calib_s, self.calib_r,
                    self.calib_c, self.calib_sp, self.calib_door, self.calib_rest,
                    self.testnav_btn, self.preview_btn):
            btn.config(state=sa)
        self.stop_btn.config(state=sb)

    def _save_all(self):
        save_config(self.stoves, self.recipe, self._get_settings())

    def _start(self):
        self._save_all()
        s = self._get_settings()
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
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}")
            return

        scale = max(game_w / MOLE_W, game_h / MOLE_H)

        def to_px(mx, my):
            return int(mx * scale), int(my * scale)

        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)

        def dot(mx, my, color, label=""):
            x, y = to_px(mx, my)
            r = 8
            draw.ellipse([x-r, y-r, x+r, y+r], fill=color, outline="white")
            if label:
                draw.text((x+r+2, y-8), label, fill=color)

        # 鍋爐
        for i, (sx, sy) in enumerate(self.stoves):
            dot(sx, sy, "lime", f"爐{i+1}")

        # 食譜元素
        r = self.recipe
        dot(*r["left_arrow"],  "cyan",   "←")
        dot(*r["right_arrow"], "cyan",   "→")
        dot(*r["close"],       "red",    "X")
        for i, pt in enumerate(r["page_tabs"]):
            dot(*pt, "yellow", str(i+1))
        for i, pt in enumerate(r["dishes"]):
            dot(*pt, "orange", f"菜{i+1}")
        dot(*r["check_pt"],    "white",  "偵測")
        dot(*r.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"]), "magenta", "確認")

        # 顯示
        disp_scale = min(900/game_w, 600/game_h, 1.0)
        disp = img.resize((int(game_w*disp_scale), int(game_h*disp_scale)), Image.LANCZOS)

        win = tk.Toplevel(self.root)
        win.title("座標預覽（綠=鍋爐 橙=菜色 黃=頁碼 青=箭頭 紅=X 白=偵測點）")
        photo = ImageTk.PhotoImage(disp)
        tk.Label(win, image=photo).pack()
        win.photo = photo

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
        self._save_all()
        messagebox.showinfo("完成", f"確認：{pts[0]}　取消：{pts[1]}\n已儲存。")

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
        self._save_all()

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
            self._save_all()
            if messagebox.askyesno("繼續", "請手動走出餐廳後，按「是」截圖校準入口。"):
                hwnd = self._get_hwnd()
                if hwnd:
                    CalibrationWindow(self.root, hwnd, ["入口（餐廳外往內的門口）"], self._done_door_in)

    def _done_door_waypoint(self, pts):
        self._extra_settings["door_waypoint"] = list(pts[0])
        self.bot.settings["door_waypoint"] = list(pts[0])
        self._save_all()
        if messagebox.askyesno("繼續", f"走動點已儲存：{pts[0]}\n\n請走到入口位置後，按「是」截圖校準入口。"):
            hwnd = self._get_hwnd()
            if hwnd:
                CalibrationWindow(self.root, hwnd, ["入口（餐廳外往內的門口）"], self._done_door_in)

    def _done_door_in(self, pts):
        self._extra_settings["door_in"] = list(pts[0])
        self.bot.settings["door_in"] = list(pts[0])
        self._save_all()
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
            self._save_all()
            win.destroy()
            messagebox.showinfo("完成",
                f"餐廳確認點：({mx}, {my})  RGB{rgb}\n已儲存。\n\n"
                "機器人每輪掃描前會確認這個顏色，\n不在餐廳時會自動嘗試回去。")

        canvas.bind("<Button-1>", on_pick)

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
            ("腐壞",       "食物腐壞特徵點 → 自動清除",             "spoiled_color", "spoiled_offset"),
            ("時鐘（烹飪）", "橙色圓形時鐘 → 烹飪中跳過",           "clock_color",   "clock_offset"),
            ("做完（黃光）", "食物做好黃光 → 自動收菜再重做",         "done_color",    "done_offset"),
        ]

        for label, hint, color_key, offset_key in states:
            state_name = color_key.replace("_color", "")
            points = self._extra_settings.get(f"{state_name}_points") or []
            color  = self._extra_settings.get(color_key)
            offset = self._extra_settings.get(offset_key) if offset_key else None
            if points:
                badge = f"✓ {len(points)} 個校準點"
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
        多點校準：使用者可在截圖上點多個備用點（最多 4 個），
        儲存為 <state>_points 格式 [dx, dy, r, g, b]，
        偵測時任一點符合即算偵測到，可避免 NPC 對話框或坐騎遮擋時失準。
        """
        # points_key = "done_points" / "clock_points" / "spoiled_points"
        state_name = color_key.replace("_color", "")          # done / clock / spoiled
        points_key = f"{state_name}_points"

        hwnd = self._get_hwnd()
        if not hwnd: return
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}")
            return

        sg = max(game_w / MOLE_W, game_h / MOLE_H)
        disp_scale = min(900 / game_w, 580 / game_h, 1.0)
        img_rgb = img.convert("RGB")
        disp  = img.resize((int(game_w * disp_scale), int(game_h * disp_scale)))
        photo = ImageTk.PhotoImage(disp)

        hints = {
            "clock_offset":   "點 1~4 個橙色時鐘圓圈上的位置",
            "done_offset":    "點 1~4 個食物做好黃光的位置",
            "spoiled_offset": "點 1~4 個鍋爐正上方黑煙的位置（不同高度都可以點）",
        }
        hint = hints.get(offset_key, "點 1~4 個目標位置，點完按「完成」")

        # 載入已有的校準點，顯示在畫面上
        existing = list(self._extra_settings.get(points_key) or [])
        pending  = []   # 新點擊的點

        win = tk.Toplevel(self.root)
        win.title(f"校準「{label}」（多點）")
        win.grab_set()

        ttk.Label(win, text=f"▶ {hint}\n最多可加 4 個點，NPC 擋住其中一個時其他點還能偵測到。",
                  padding=8, wraplength=500).pack()
        count_lbl = ttk.Label(win, text="", foreground="blue", padding=(8, 0))
        count_lbl.pack()

        canvas = tk.Canvas(win,
                           width=int(game_w * disp_scale),
                           height=int(game_h * disp_scale),
                           cursor="crosshair")
        canvas.pack(padx=8, pady=4)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.photo = photo

        dot_colors = ["red", "blue", "green", "purple"]

        def draw_dot(ex, ey, idx, is_existing=False):
            r = 7
            col = dot_colors[idx % len(dot_colors)]
            style = "dashed" if is_existing else "solid"
            canvas.create_oval(ex-r, ey-r, ex+r, ey+r,
                               outline=col, width=3, dash=(4,2) if is_existing else ())
            canvas.create_text(ex, ey, text=str(idx+1), fill=col,
                               font=("Arial", 9, "bold"))

        def update_count():
            total = len(existing) + len(pending)
            count_lbl.config(text=f"目前 {total} 個點（灰圈=已存，彩圈=本次新增）")

        # 畫出既有的點
        if existing and self.stoves:
            ref = self.stoves[0]
            for i, (dx, dy, r, g, b) in enumerate(existing):
                ex = (ref[0] + dx) * sg * disp_scale
                ey = (ref[1] + dy) * sg * disp_scale
                draw_dot(int(ex), int(ey), i, is_existing=True)
        update_count()

        def on_pick(event):
            total = len(existing) + len(pending)
            if total >= 4:
                count_lbl.config(text="已達 4 個上限，請按完成或先清除", foreground="red")
                return
            px  = min(int(event.x / disp_scale), game_w - 1)
            py  = min(int(event.y / disp_scale), game_h - 1)
            mx  = int(px / sg)
            my  = int(py / sg)
            rgb = img_rgb.getpixel((px, py))
            if not self.stoves:
                return
            nearest = min(self.stoves, key=lambda s: abs(s[0]-mx) + abs(s[1]-my))
            dx, dy  = mx - nearest[0], my - nearest[1]
            pending.append([dx, dy, rgb[0], rgb[1], rgb[2]])
            draw_dot(int(event.x), int(event.y), len(existing) + len(pending) - 1)
            update_count()

        def on_save():
            merged = existing + pending
            if not merged:
                messagebox.showwarning("提示", "還沒有點任何位置。")
                return
            self._extra_settings[points_key] = merged
            self.bot.settings[points_key]    = merged
            # 同步舊格式（取第一個點，保持舊版偵測測試 Δ 顯示正確）
            if merged:
                dx, dy, r, g, b = merged[0]
                self._extra_settings[color_key]  = [r, g, b]
                self.bot.settings[color_key]     = [r, g, b]
                self._extra_settings[offset_key] = [dx, dy]
                self.bot.settings[offset_key]    = [dx, dy]
            self._save_all()
            win.destroy()
            messagebox.showinfo("完成",
                f"「{label}」已儲存 {len(merged)} 個校準點。\n"
                "偵測時任一個符合即算偵測到。")

        def on_clear():
            existing.clear()
            pending.clear()
            self._extra_settings[points_key] = []
            self.bot.settings[points_key]    = []
            self._save_all()
            canvas.delete("all")
            canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            update_count()
            count_lbl.config(foreground="blue")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)
        ttk.Button(btn_frame, text="完成",    command=on_save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="清除全部", command=on_clear).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消",    command=win.destroy).pack(side=tk.LEFT, padx=6)

        canvas.bind("<Button-1>", on_pick)

        canvas.bind("<Button-1>", on_pick)

    def _calib_stoves(self):
        hwnd = self._get_hwnd()
        if not hwnd: return
        prompts = [f"第 {i+1} 個鍋爐" for i in range(6)]
        CalibrationWindow(self.root, hwnd, prompts, self._done_stoves)

    def _done_stoves(self, pts):
        self.stoves = pts
        self.bot.stoves = pts
        self._save_all()
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
        self._save_all()
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

        ttk.Label(win, text="每 0.5 秒掃一次所有鍋爐，Δ 值越小代表越接近校準顏色，< threshold 表示偵測到。",
                  padding=(10, 8, 10, 4), wraplength=480).pack()

        threshold = self.bot.settings.get("state_threshold", 40)
        ttk.Label(win, text=f"目前 threshold = {threshold}（校準狀態色介面可調整）",
                  foreground="gray", padding=(10, 0, 10, 6)).pack()

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill=tk.BOTH)

        # 表頭
        headers = ["鍋爐", "座標", "狀態", "done Δ", "clock Δ", "spoiled Δ"]
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

        def refresh():
            if stop_event.is_set() or not win.winfo_exists():
                return
            s = self.bot.settings
            threshold = s.get("state_threshold", 40)

            done_color    = s.get("done_color")
            done_off      = s.get("done_offset")    or [0, 0]
            clock_color   = s.get("clock_color")
            clock_off     = s.get("clock_offset")   or [0, 0]
            spoiled_color = s.get("spoiled_color")
            spoiled_off   = s.get("spoiled_offset") or [0, 0]

            for i, (sx, sy) in enumerate(self.bot.stoves):
                state = self.bot.detect_stove_state(sx, sy)

                def delta_str(color, off, spread=4):
                    if not color:
                        return "未校準"
                    ox, oy = off
                    mx, my = sx + ox, sy + oy
                    best = 999
                    for ddx, ddy in ((0,0),(spread,0),(-spread,0),(0,spread),(0,-spread)):
                        d = self.bot.color_diff(
                            self.bot.get_pixel(mx+ddx, my+ddy), tuple(color))
                        if d < best:
                            best = d
                    mark = " ✓" if best < threshold else ""
                    return f"{best}{mark}"

                done_d    = delta_str(done_color,    done_off)
                clock_d   = delta_str(clock_color,   clock_off)
                spoiled_d = delta_str(spoiled_color, spoiled_off, spread=6)

                state_color = {"cooking": "blue", "done": "orange",
                               "spoiled": "red",  "unknown": "gray"}.get(state, "gray")

                def update_row(idx=i, st=state, sc=state_color,
                               dd=done_d, cd=clock_d, sd=spoiled_d):
                    if not win.winfo_exists(): return
                    row_labels[idx][0].config(text=str(idx+1))
                    row_labels[idx][1].config(text=f"{self.bot.stoves[idx]}")
                    row_labels[idx][2].config(text=st, foreground=sc)
                    row_labels[idx][3].config(text=dd)
                    row_labels[idx][4].config(text=cd)
                    row_labels[idx][5].config(text=sd)

                win.after(0, update_row)

            win.after(500, refresh)

        def on_close():
            stop_event.set()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)
        threading.Thread(target=refresh, daemon=True).start()

    def _on_status(self, msg, error=False):
        color = "red" if error else ("gray" if msg == "已停止" else "green")
        self.root.after(0, lambda: self.status.config(text=f"狀態：{msg}", foreground=color))
        if msg == "已停止" or error:
            self.root.after(0, lambda: self._set_running(False))
        if error:
            self.root.after(0, lambda: messagebox.showerror("錯誤", msg))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

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
    "page": 6, "dish": 1, "cook_minutes": 20,
    "restart_delay": 30, "antlag_minutes": 5,
    "cooking_color":  None,   # 烹飪中
    "done_color":     None,   # 完成/可收菜
    "utensils_color": None,   # 餐具/等放食材
    "spoiled_color":  None,   # 腐壞
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

class RestaurantBot:
    def __init__(self, stoves, recipe, settings):
        self.hwnd     = None
        self._stop    = threading.Event()
        self.stoves   = stoves
        self.recipe   = recipe
        self.settings = settings

    def detect_stove_state(self, sx, sy):
        """
        回傳鍋爐狀態字串：
          "cooking" | "done" | "utensils" | "spoiled" | "unknown"
        按顏色樣本比對，未校準的狀態會略過回傳 unknown
        """
        threshold = self.settings.get("state_threshold", 40)
        pixel = self.get_pixel(sx, sy)
        for state in ("cooking", "done", "utensils", "spoiled"):
            color = self.settings.get(f"{state}_color")
            if color and self.color_diff(pixel, tuple(color)) < threshold:
                return state
        return "unknown"

    def is_stove_spoiled(self, sx, sy):
        return self.detect_stove_state(sx, sy) == "spoiled"

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

    def close_recipe(self, sx, sy, on_status=None):
        """點 X 按鈕關閉食譜（用真實滑鼠）"""
        close = self.recipe.get("close", (0, 0))
        if close != (0, 0):
            if on_status: on_status(f"關閉食譜：點 X ({close[0]},{close[1]})")
            self.click_real(*close, delay=0.5)
        else:
            if on_status: on_status("警告：X 按鈕座標未校準 (0,0)，無法關閉食譜")

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
        on_status("防卡頓：前往地圖…")
        self.click(*MAP_BTN, delay=3.0)
        if self._stop.is_set(): return
        on_status("防卡頓：回到餐廳…")
        self.click(*HOME_BTN, delay=1.0)
        self.click(*RESTAURANT_BTN, delay=3.0)

    def wait_with_antlag(self, total_seconds, interval_seconds, on_status, msg):
        elapsed = 0
        while elapsed < total_seconds and not self._stop.is_set():
            chunk = min(interval_seconds, total_seconds - elapsed)
            rem = total_seconds - elapsed
            on_status(f"{msg}（剩餘 {int(rem//60)} 分 {int(rem%60)} 秒）")
            if not self.wait(chunk):
                return False
            elapsed += chunk
            if elapsed < total_seconds and not self._stop.is_set():
                self.leave_and_return(on_status)
        return not self._stop.is_set()

    def navigate_to_page(self, target_page):
        r = self.recipe
        for _ in range(10):
            if self._stop.is_set(): return
            self.click_real(*r["left_arrow"], delay=0.15)

        tabs = r["page_tabs"]
        if target_page <= 5:
            self.click_real(*tabs[target_page - 1], delay=0.3)
        else:
            for _ in range(target_page - 5):
                if self._stop.is_set(): return
                self.click_real(*r["right_arrow"], delay=0.15)
            self.click_real(*tabs[4], delay=0.3)

        time.sleep(0.3)

    def is_recipe_open(self, closed_color, threshold=40):
        """比對 check_pt 目前顏色與「食譜關閉」基準色，判斷食譜是否開啟"""
        current = self.get_pixel(*self.recipe["check_pt"])
        return self.color_diff(current, closed_color) > threshold

    def ensure_recipe_closed(self, closed_color, on_status=None):
        """若食譜目前是開啟狀態，嘗試關閉它"""
        if not self.is_recipe_open(closed_color):
            return True
        if on_status: on_status(f"偵測到食譜已開啟（check_pt 顏色與基準不符），先關閉…")
        close = self.recipe.get("close", (0, 0))
        if close == (0, 0):
            if on_status: on_status("警告：X 按鈕未校準，無法自動關閉食譜")
            return False
        self.click(*close, delay=0.5)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if self._stop.is_set(): return False
            time.sleep(0.2)
            if not self.is_recipe_open(closed_color):
                if on_status: on_status("食譜已關閉 ✓")
                return True
        if on_status: on_status("警告：無法確認食譜是否關閉，繼續執行…")
        return False

    def setup_stove(self, sx, sy, page, dish, on_status=None):
        def log(msg):
            if on_status: on_status(msg)

        confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        cancel_btn  = self.recipe.get("cancel_btn",  DEFAULT_RECIPE["cancel_btn"])
        check       = self.recipe["check_pt"]
        dish_pt     = self.recipe["dishes"][dish - 1]

        # ── 偵測鍋爐狀態 ──────────────────────────────
        state = self.detect_stove_state(sx, sy)
        log(f"鍋爐 ({sx},{sy}) 狀態：{state}")

        if state == "cooking":
            log("烹飪中，跳過")
            return

        if state == "done":
            log("食物完成，收菜…")
            self.click(sx, sy, delay=0.8)
            if self._stop.is_set(): return
            time.sleep(0.5)
            state = "empty"   # 繼續開食譜

        if state == "spoiled":
            log("腐壞食物，清除…")
            self.click(sx, sy, delay=0.3)   # 打開彈窗
            time.sleep(0.5)
            self.click_real(*confirm_btn, delay=1.0)
            if self._stop.is_set(): return
            time.sleep(0.3)
            state = "empty"   # 繼續開食譜

        if state == "utensils":
            log("餐具狀態，放入食材…")
            self.click(sx, sy, delay=1.2)
            if self._stop.is_set(): return
            log("開始烹飪…")
            self.click(sx, sy, delay=0.5)
            log(f"鍋爐 ({sx},{sy}) 烹飪中 ✓")
            return

        # ── state == "empty" 或 "unknown"：開食譜 ────
        recipe_opened = False
        for attempt in range(2):
            if self._stop.is_set(): return
            log(f"點鍋爐…" + ("（重試）" if attempt else ""))
            pre = self.get_pixel(*check)
            self.click(sx, sy, delay=0.3)
            ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)

            if ok:
                log(f"食譜已開啟 ✓  check_pt({check[0]},{check[1]}): {c_before}→{c_after}")
                recipe_opened = True
                break

            # 食譜沒開，彈窗出現
            if self.is_stove_spoiled(sx, sy):
                log(f"點確認清除腐壞 ({confirm_btn[0]},{confirm_btn[1]})…")
                self.click_real(*confirm_btn, delay=1.0)
            else:
                log(f"做菜中，點取消 ({cancel_btn[0]},{cancel_btn[1]})，跳過")
                self.click_real(*cancel_btn, delay=0.5)
                return

        if not recipe_opened:
            log(f"鍋爐 ({sx},{sy}) 無法開啟食譜，跳過")
            return
        if self._stop.is_set(): return

        # ── 切換頁面 ──────────────────────────────────
        log(f"切換到第 {page} 頁…")
        self.navigate_to_page(page)
        if self._stop.is_set(): return

        # ── 點菜色，等食譜關閉 ────────────────────────
        log(f"點菜色 {dish}，座標 ({dish_pt[0]},{dish_pt[1]})…")
        pre = self.get_pixel(*check)
        self.click_real(*dish_pt, delay=0.3)
        ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)
        if not ok:
            log(f"點菜後食譜沒有關閉（{c_before}），請重新校準菜格座標")
            return
        log(f"食譜已關閉 ✓ ({c_before}→{c_after})")
        if self._stop.is_set(): return

        # ── 放入食材 ──────────────────────────────────
        time.sleep(0.5)
        log("放入食材…")
        self.click(sx, sy, delay=1.2)
        if self._stop.is_set(): return

        # ── 開始烹飪 ──────────────────────────────────
        log("開始烹飪…")
        self.click(sx, sy, delay=0.5)
        log(f"鍋爐 ({sx},{sy}) 烹飪中 ✓")

    def run(self, page, dish, cook_minutes, restart_delay, antlag_minutes, on_status):
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗", error=True)
            return

        self._stop.clear()
        antlag_sec = antlag_minutes * 60 if antlag_minutes > 0 else cook_minutes * 60

        while not self._stop.is_set():
            # 設定所有鍋爐
            for i, (sx, sy) in enumerate(self.stoves):
                if self._stop.is_set(): break
                on_status(f"設定鍋爐 {i+1}/{len(self.stoves)}…")
                self.setup_stove(sx, sy, page, dish, on_status)
                if not self.wait(0.5): break

            if self._stop.is_set(): break

            # 等待烹飪完成（含防卡頓）
            if not self.wait_with_antlag(cook_minutes * 60, antlag_sec, on_status, "烹飪中"): break

            # 收菜
            on_status("收菜中…")
            for sx, sy in self.stoves:
                if self._stop.is_set(): break
                self.click(sx, sy, delay=0.8)

            if self._stop.is_set(): break
            on_status(f"等待 {restart_delay} 秒後重新開始…")
            if not self.wait(restart_delay): break

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
        _extra_keys = ("cooking_color", "done_color", "utensils_color", "spoiled_color", "state_threshold")
        self._extra_settings = {k: settings[k] for k in _extra_keys}
        self.bot = RestaurantBot(self.stoves, self.recipe, settings)
        self._build_ui(settings)

    def _build_ui(self, settings):
        f = ttk.Frame(self.root, padding=15)
        f.pack()

        rows = [
            ("食譜頁數 (1~9)",           "page",           1,   9),
            ("菜的位置 (1~6)",           "dish",           1,   6),
            ("烹飪時間（分鐘）",         "cook_minutes",   1,  99),
            ("收菜後延遲（秒）",         "restart_delay",  0, 600),
            ("防卡頓間隔（分鐘，0=關）", "antlag_minutes", 0,  99),
        ]
        self.vars = {}
        for i, (lbl, key, lo, hi) in enumerate(rows):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky=tk.W, pady=4, padx=(0,10))
            v = tk.IntVar(value=settings[key])
            ttk.Spinbox(f, from_=lo, to=hi, textvariable=v, width=8).grid(row=i, column=1, pady=4)
            self.vars[key] = v

        self.status = ttk.Label(f, text="狀態：待機", foreground="gray")
        self.status.grid(row=len(rows), column=0, columnspan=2, pady=(12, 4))

        btn_f = ttk.Frame(f)
        btn_f.grid(row=len(rows)+1, column=0, columnspan=2, pady=(0, 4))

        self.start_btn  = ttk.Button(btn_f, text="開始",     command=self._start)
        self.stop_btn   = ttk.Button(btn_f, text="停止",     command=self._stop, state=tk.DISABLED)
        self.calib_s    = ttk.Button(btn_f, text="校準鍋爐", command=self._calib_stoves)
        self.calib_r    = ttk.Button(btn_f, text="校準食譜", command=self._calib_recipe)
        self.calib_c    = ttk.Button(btn_f, text="校準彈窗按鈕", command=self._calib_cancel)
        self.calib_sp   = ttk.Button(btn_f, text="校準狀態色", command=self._calib_state_colors)
        self.preview_btn= ttk.Button(btn_f, text="預覽座標", command=self._preview_coords)

        for btn in (self.start_btn, self.stop_btn, self.calib_s, self.calib_r,
                    self.calib_c, self.calib_sp, self.preview_btn):
            btn.pack(side=tk.LEFT, padx=4)

    def _get_settings(self):
        s = {k: v.get() for k, v in self.vars.items()}
        s.update(self._extra_settings)  # 合併 spoiled_color / spoiled_threshold
        return s

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        self.start_btn.config(state=sa)
        self.calib_s.config(state=sa)
        self.calib_r.config(state=sa)
        self.calib_c.config(state=sa)
        self.calib_sp.config(state=sa)
        self.stop_btn.config(state=sb)

    def _save_all(self):
        save_config(self.stoves, self.recipe, self._get_settings())

    def _start(self):
        self._save_all()
        s = self._get_settings()
        self._set_running(True)
        threading.Thread(
            target=self.bot.run,
            args=(s["page"], s["dish"], s["cook_minutes"],
                  s["restart_delay"], s["antlag_minutes"], self._on_status),
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

    def _calib_state_colors(self):
        """開啟鍋爐狀態顏色校準選擇器"""
        states = [
            ("cooking_color",  "烹飪中",       "鍋爐正在烹飪（點擊會出現彈窗）"),
            ("done_color",     "完成/可收菜",   "食物做好、鍋爐發亮"),
            ("utensils_color", "餐具/等放食材", "選完菜後，鍋爐顯示餐具圖示"),
            ("spoiled_color",  "腐壞",         "食物變黑/腐壞"),
        ]

        win = tk.Toplevel(self.root)
        win.title("校準鍋爐狀態顏色")
        win.grab_set()
        win.resizable(False, False)

        ttk.Label(win, text="選擇要校準的鍋爐狀態：", padding=(12, 10, 12, 2)).pack()
        ttk.Label(
            win,
            text="先讓對應鍋爐處於該狀態，再點下方按鈕截圖取色。",
            foreground="gray", padding=(12, 0, 12, 8)
        ).pack()

        for key, label, hint in states:
            color = self._extra_settings.get(key)
            badge = f"✓ {tuple(color)}" if color else "未校準"
            row = ttk.Frame(win)
            row.pack(fill=tk.X, padx=12, pady=3)
            ttk.Button(
                row, text=f"校準「{label}」",
                command=lambda k=key, l=label, w=win: (w.destroy(), self._calib_one_state(k, l))
            ).pack(side=tk.LEFT)
            ttk.Label(row, text=f"  {hint}  [{badge}]", foreground="gray").pack(side=tk.LEFT)

        ttk.Button(win, text="關閉", command=win.destroy).pack(pady=8)

    def _calib_one_state(self, color_key, label):
        """截圖後讓使用者點鍋爐，取得顏色樣本"""
        hwnd = self._get_hwnd()
        if not hwnd: return
        try:
            img, game_w, game_h = capture_window(hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}")
            return

        disp_scale = min(900 / game_w, 580 / game_h, 1.0)
        disp = img.resize((int(game_w * disp_scale), int(game_h * disp_scale)))
        photo = ImageTk.PhotoImage(disp)

        win = tk.Toplevel(self.root)
        win.title(f"校準「{label}」— 點一下鍋爐取色")
        win.grab_set()
        ttk.Label(win, text=f"▶ 點一下【{label}】狀態的鍋爐位置", padding=8).pack()
        canvas = tk.Canvas(win,
                           width=int(game_w * disp_scale),
                           height=int(game_h * disp_scale),
                           cursor="crosshair")
        canvas.pack(padx=8, pady=8)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.photo = photo

        def on_pick(event):
            px = min(int(event.x / disp_scale), game_w - 1)
            py = min(int(event.y / disp_scale), game_h - 1)
            rgb = img.convert("RGB").getpixel((px, py))
            self._extra_settings[color_key] = list(rgb)
            self.bot.settings[color_key] = list(rgb)
            self._save_all()
            win.destroy()
            messagebox.showinfo("完成", f"「{label}」顏色已儲存：RGB{rgb}")

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

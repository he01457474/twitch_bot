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
    "check_pt":    (490, 300),   # 食譜中心偵測點（判斷食譜是否開啟）
}
DEFAULT_SETTINGS = {
    "page": 6, "dish": 1, "cook_minutes": 20,
    "restart_delay": 30, "antlag_minutes": 5,
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
    hwndDC = win32gui.GetWindowDC(hwnd)
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
    def __init__(self, stoves, recipe):
        self.hwnd   = None
        self._stop  = threading.Event()
        self.stoves = stoves
        self.recipe = recipe

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
        """真實滑鼠點擊（帶到前景），適合食譜彈出視窗等 SendMessage 無效的元素"""
        if not self.hwnd:
            return
        rect  = win32gui.GetClientRect(self.hwnd)
        w, h  = rect[2], rect[3]
        scale = max(w / MOLE_W, h / MOLE_H)
        cx, cy = int(mole_x * scale), int(mole_y * scale)
        try:
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.1)
            sx, sy = win32gui.ClientToScreen(self.hwnd, (cx, cy))
            win32api.SetCursorPos((sx, sy))
            time.sleep(0.05)
            win32api.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            time.sleep(0.08)
            win32api.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
        except Exception as e:
            pass
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

    def setup_stove(self, sx, sy, page, dish, closed_color, on_status=None):
        def log(msg):
            if on_status: on_status(msg)

        def err(msg):
            self._stop.set()
            if on_status: on_status(msg, error=True)

        check = self.recipe["check_pt"]
        dish_pt = self.recipe["dishes"][dish - 1]

        log(f"[鍋爐 ({sx},{sy})] 開始設定")

        # 先確認食譜是關閉狀態
        self.ensure_recipe_closed(closed_color, on_status)

        # 步驟 1：點鍋爐，偵測食譜是否開啟（最多重試 3 次）
        for attempt in range(3):
            if self._stop.is_set(): return
            log(f"點鍋爐 ({sx},{sy})，等待食譜（偵測點 {check}）…")
            pre = self.get_pixel(*check)          # 點擊前先截基準色
            self.click(sx, sy, delay=0.1)
            ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=5.0, baseline=pre)
            if ok:
                log(f"食譜已開啟 ✓  偵測色 {c_before}→{c_after}")
                break
            log(f"食譜未開啟 ✗  偵測點 {check} 顏色未變（{c_before}），第 {attempt+1}/3 次")
        else:
            err(f"3 次仍無法開啟食譜\n鍋爐座標 ({sx},{sy})，偵測點 {check} 顏色未變（{c_before}）\n請確認鍋爐座標或偵測點是否正確")
            return

        if self._stop.is_set(): return
        log(f"切換到第 {page} 頁…")
        self.navigate_to_page(page)

        # 步驟 2：點菜，偵測食譜是否關閉（最多重試 3 次）
        for attempt in range(3):
            if self._stop.is_set():
                self.close_recipe(sx, sy, on_status)
                return
            log(f"點菜色 {dish} ({dish_pt[0]},{dish_pt[1]})…" + (f"（第 {attempt+1} 次）" if attempt else ""))
            pre = self.get_pixel(*check)          # 點擊前先截基準色
            self.click_real(*dish_pt, delay=0.1)
            ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)
            if ok:
                log(f"烹飪開始 ✓  偵測色 {c_before}→{c_after}")
                return
            log(f"點菜失敗 ✗  偵測點 {check} 顏色未變（{c_before}）")
            if attempt < 2:
                self.close_recipe(sx, sy, on_status)
                time.sleep(0.5)
                log(f"重新開啟食譜…")
                for retry in range(3):
                    if self._stop.is_set(): return
                    pre2 = self.get_pixel(*check)  # 點擊前先截基準色
                    self.click(sx, sy, delay=0.1)
                    ok2, cb2, ca2 = self.wait_for_pixel_change(*check, timeout=5.0, baseline=pre2)
                    if ok2:
                        log(f"食譜重新開啟 ✓  偵測色 {cb2}→{ca2}")
                        self.navigate_to_page(page)
                        break
                    log(f"重開食譜失敗 ✗（{cb2}），第 {retry+1}/3 次")
                else:
                    err(f"關閉後 3 次仍無法重新開啟食譜\n鍋爐座標 ({sx},{sy})，偵測點 {check}")
                    return

        err(f"點菜 3 次失敗\n菜格座標 ({dish_pt[0]},{dish_pt[1]}) 可能不正確，請重新校準食譜")
        self.close_recipe(sx, sy, on_status)

    def run(self, page, dish, cook_minutes, restart_delay, antlag_minutes, on_status):
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗", error=True)
            return

        self._stop.clear()
        antlag_sec = antlag_minutes * 60 if antlag_minutes > 0 else cook_minutes * 60

        # 截「食譜關閉」基準色（啟動時食譜應該是關的）
        on_status("截取食譜關閉基準色…")
        closed_color = self.get_pixel(*self.recipe["check_pt"])
        on_status(f"基準色已截取：{closed_color}（食譜關閉狀態）")

        while not self._stop.is_set():
            for i, (sx, sy) in enumerate(self.stoves):
                if self._stop.is_set(): break
                on_status(f"設定鍋爐 {i+1}/{len(self.stoves)}…")
                self.setup_stove(sx, sy, page, dish, closed_color, on_status)
                if not self.wait(0.5): break

            if self._stop.is_set(): break
            if not self.wait_with_antlag(cook_minutes * 60, antlag_sec, on_status, "烹飪中"): break

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
        self.bot = RestaurantBot(self.stoves, self.recipe)
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

        self.start_btn  = ttk.Button(btn_f, text="開始",   command=self._start)
        self.stop_btn   = ttk.Button(btn_f, text="停止",   command=self._stop, state=tk.DISABLED)
        self.calib_s    = ttk.Button(btn_f, text="校準鍋爐", command=self._calib_stoves)
        self.calib_r    = ttk.Button(btn_f, text="校準食譜", command=self._calib_recipe)

        for btn in (self.start_btn, self.stop_btn, self.calib_s, self.calib_r):
            btn.pack(side=tk.LEFT, padx=4)

    def _get_settings(self):
        return {k: v.get() for k, v in self.vars.items()}

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        self.start_btn.config(state=sa)
        self.calib_s.config(state=sa)
        self.calib_r.config(state=sa)
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
        self.recipe = {
            "left_arrow":  pts[0],
            "right_arrow": pts[1],
            "close":       pts[2],
            "page_tabs":   pts[3:8],
            "dishes":      pts[8:14],
            "check_pt":    pts[14],
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

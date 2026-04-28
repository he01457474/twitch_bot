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

DEFAULT_STOVES = [
    (175, 215), (175, 265), (175, 315),
    (785, 215), (785, 265), (785, 315),
]

LEFT_ARROW   = (245, 478)
RIGHT_ARROW  = (715, 478)
RECIPE_CLOSE = (733, 110)

DISH_POS = [
    (345, 245), (490, 245), (635, 245),
    (345, 385), (490, 385), (635, 385),
]

# 防卡頓：離開餐廳 → 去地圖 → 回來
MAP_BTN        = (33,  505)   # 地圖按鈕
HOME_BTN       = (880, 538)   # 家園按鈕
RESTAURANT_BTN = (880, 449)   # 家園選單裡的餐廳


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return [tuple(s) for s in data.get("stoves", DEFAULT_STOVES)]
        except Exception:
            pass
    return list(DEFAULT_STOVES)


def save_config(stoves):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"stoves": stoves}, f)
    except Exception:
        pass


def capture_window(hwnd):
    rect = win32gui.GetClientRect(hwnd)
    w, h = rect[2], rect[3]
    hwndDC  = win32gui.GetWindowDC(hwnd)
    mfcDC   = win32ui.CreateDCFromHandle(hwndDC)
    saveDC  = mfcDC.CreateCompatibleDC()
    bmp     = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    info    = bmp.GetInfo()
    raw     = bmp.GetBitmapBits(True)
    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]), raw, "raw", "BGRX", 0, 1)
    return img, w, h


class CalibrationWindow:
    def __init__(self, parent, hwnd, on_done):
        self.hwnd   = hwnd
        self.on_done = on_done
        self.clicks  = []
        self.display_scale = 1.0

        self.win = tk.Toplevel(parent)
        self.win.title("校準鍋爐位置")
        self.win.grab_set()
        self._build()

    def _build(self):
        ttk.Label(self.win,
                  text="請依序點擊 6 個鍋爐位置（點完自動關閉）",
                  padding=8).pack()
        self.info = ttk.Label(self.win, text="▶ 第 1 個鍋爐", foreground="blue", padding=4)
        self.info.pack()

        try:
            img, game_w, game_h = capture_window(self.hwnd)
        except Exception as e:
            messagebox.showerror("錯誤", f"截圖失敗：{e}", parent=self.win)
            self.win.destroy()
            return

        self.game_w, self.game_h = game_w, game_h
        max_w, max_h = 900, 580
        scale = min(max_w / game_w, max_h / game_h, 1.0)
        self.display_scale = scale
        disp_img = img.resize((int(game_w * scale), int(game_h * scale)))
        self.photo = ImageTk.PhotoImage(disp_img)

        self.canvas = tk.Canvas(self.win,
                                width=int(game_w * scale),
                                height=int(game_h * scale),
                                cursor="crosshair")
        self.canvas.pack(padx=8, pady=8)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        self.canvas.bind("<Button-1>", self._on_click)

    def _on_click(self, event):
        scale_game = max(self.game_w / MOLE_W, self.game_h / MOLE_H)
        cx = event.x / self.display_scale
        cy = event.y / self.display_scale
        mole_x = int(cx / scale_game)
        mole_y = int(cy / scale_game)
        self.clicks.append((mole_x, mole_y))
        n = len(self.clicks)

        r = 6
        self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r,
                                fill="red", outline="white", width=2)
        self.canvas.create_text(event.x+12, event.y, text=str(n),
                                fill="red", font=("Arial", 11, "bold"))

        if n < 6:
            self.info.config(text=f"▶ 第 {n+1} 個鍋爐")
        else:
            self.info.config(text="✔ 校準完成！")
            self.win.after(800, self._finish)

    def _finish(self):
        self.on_done(self.clicks)
        self.win.destroy()


class RestaurantBot:
    def __init__(self):
        self.hwnd   = None
        self._stop  = threading.Event()
        self.stoves = load_config()

    def find_window(self):
        found = []
        def cb(hwnd, _):
            if "Adobe Flash Player" in win32gui.GetWindowText(hwnd) and win32gui.IsWindowVisible(hwnd):
                found.append(hwnd)
        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    def click(self, mole_x, mole_y, delay=0.1):
        if not self.hwnd:
            return
        rect  = win32gui.GetClientRect(self.hwnd)
        w, h  = rect[2], rect[3]
        scale = max(w / MOLE_W, h / MOLE_H)
        cx    = int(mole_x * scale)
        cy    = int(mole_y * scale)
        lp    = (cy << 16) | (cx & 0xFFFF)
        win32api.SendMessage(self.hwnd, 0x201, 0, lp)
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
        """離開餐廳去地圖繞一圈，避免卡頓"""
        on_status("防卡頓：前往地圖…")
        self.click(*MAP_BTN, delay=3.0)
        if self._stop.is_set(): return
        on_status("防卡頓：回到餐廳…")
        self.click(*HOME_BTN, delay=1.0)
        self.click(*RESTAURANT_BTN, delay=3.0)

    def wait_with_antlag(self, total_seconds, interval_seconds, on_status, status_msg):
        """等待期間定時離開餐廳防卡頓"""
        elapsed = 0
        while elapsed < total_seconds and not self._stop.is_set():
            chunk = min(interval_seconds, total_seconds - elapsed)
            remaining = total_seconds - elapsed
            on_status(f"{status_msg}（剩餘 {remaining // 60:.0f} 分 {remaining % 60:.0f} 秒）")
            if not self.wait(chunk):
                return False
            elapsed += chunk
            if elapsed < total_seconds and not self._stop.is_set():
                self.leave_and_return(on_status)
        return not self._stop.is_set()

    def navigate_to_page(self, target_page):
        for _ in range(10):
            if self._stop.is_set(): return
            self.click(*LEFT_ARROW, delay=0.15)
        for _ in range(target_page - 1):
            if self._stop.is_set(): return
            self.click(*RIGHT_ARROW, delay=0.15)
        time.sleep(0.3)

    def setup_stove(self, sx, sy, page, dish):
        self.click(sx, sy, delay=1.0)
        if self._stop.is_set(): return
        self.navigate_to_page(page)
        if self._stop.is_set(): return
        dx, dy = DISH_POS[dish - 1]
        self.click(dx, dy, delay=0.5)
        self.click(*RECIPE_CLOSE, delay=0.5)
        self.click(sx, sy, delay=0.5)

    def run(self, page, dish, cook_minutes, restart_delay, antlag_minutes, on_status):
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗", error=True)
            return

        self._stop.clear()
        antlag_sec = antlag_minutes * 60 if antlag_minutes > 0 else cook_minutes * 60

        while not self._stop.is_set():
            on_status("設定鍋爐中…")
            for sx, sy in self.stoves:
                if self._stop.is_set(): break
                self.setup_stove(sx, sy, page, dish)
                if not self.wait(0.8): break

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


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("摩爾莊園｜餐廳自動做菜")
        self.root.resizable(False, False)
        self.bot  = RestaurantBot()
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self.root, padding=15)
        f.pack()

        rows = [
            ("食譜頁數 (1~9)",          6,  1,   9),
            ("菜的位置 (1~6)",          1,  1,   6),
            ("烹飪時間（分鐘）",        20, 1,  99),
            ("收菜後延遲（秒）",        30, 0, 600),
            ("防卡頓間隔（分鐘，0=關）", 5, 0,  99),
        ]
        self.vars = []
        for i, (lbl, val, lo, hi) in enumerate(rows):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky=tk.W, pady=4, padx=(0, 10))
            v = tk.IntVar(value=val)
            ttk.Spinbox(f, from_=lo, to=hi, textvariable=v, width=8).grid(row=i, column=1, pady=4)
            self.vars.append(v)

        self.status = ttk.Label(f, text="狀態：待機", foreground="gray")
        self.status.grid(row=len(rows), column=0, columnspan=2, pady=(12, 6))

        btn_f = ttk.Frame(f)
        btn_f.grid(row=len(rows)+1, column=0, columnspan=2)

        self.start_btn = ttk.Button(btn_f, text="開始", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn  = ttk.Button(btn_f, text="停止", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.calib_btn = ttk.Button(btn_f, text="校準鍋爐", command=self._calibrate)
        self.calib_btn.pack(side=tk.LEFT, padx=5)

    def _set_running(self, running):
        state_a = tk.DISABLED if running else tk.NORMAL
        state_b = tk.NORMAL   if running else tk.DISABLED
        self.start_btn.config(state=state_a)
        self.calib_btn.config(state=state_a)
        self.stop_btn.config(state=state_b)

    def _start(self):
        page, dish, minutes, delay, antlag = [v.get() for v in self.vars]
        self._set_running(True)
        threading.Thread(
            target=self.bot.run,
            args=(page, dish, minutes, delay, antlag, self._on_status),
            daemon=True
        ).start()

    def _stop(self):
        self.bot.stop()
        self.stop_btn.config(state=tk.DISABLED)

    def _calibrate(self):
        hwnd = self.bot.find_window()
        if not hwnd:
            messagebox.showerror("錯誤", "找不到 Flash Player 視窗\n請先開啟遊戲")
            return
        CalibrationWindow(self.root, hwnd, self._on_calibrated)

    def _on_calibrated(self, stoves):
        self.bot.stoves = stoves
        save_config(stoves)
        messagebox.showinfo("完成", "鍋爐座標已更新並儲存！")

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

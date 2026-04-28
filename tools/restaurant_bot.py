import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import win32gui
import win32api

MOLE_W = 960
MOLE_H = 560

# 鍋爐座標（Mole 座標，若點錯需校準）
STOVES = [
    (175, 215), (175, 265), (175, 315),  # 左側三個
    (785, 215), (785, 265), (785, 315),  # 右側三個
]

# 食譜翻頁箭頭
LEFT_ARROW  = (245, 478)
RIGHT_ARROW = (715, 478)

# 食譜關閉按鈕（X）
RECIPE_CLOSE = (733, 110)

# 菜色位置（2行3列，左到右、上到下）
DISH_POS = [
    (345, 245), (490, 245), (635, 245),  # 第1、2、3格
    (345, 385), (490, 385), (635, 385),  # 第4、5、6格
]


class RestaurantBot:
    def __init__(self):
        self.hwnd = None
        self._stop = threading.Event()

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
        rect = win32gui.GetClientRect(self.hwnd)
        w, h = rect[2], rect[3]
        scale = max(w / MOLE_W, h / MOLE_H)
        cx = int(mole_x * scale)
        cy = int(mole_y * scale)
        lparam = (cy << 16) | (cx & 0xFFFF)
        win32api.SendMessage(self.hwnd, 0x201, 0, lparam)  # WM_LBUTTONDOWN
        win32api.SendMessage(self.hwnd, 0x202, 0, lparam)  # WM_LBUTTONUP
        if delay > 0:
            time.sleep(delay)

    def wait(self, seconds):
        """可中斷的等待"""
        for _ in range(int(seconds * 10)):
            if self._stop.is_set():
                return False
            time.sleep(0.1)
        return True

    def navigate_to_page(self, target_page):
        # 先點左箭頭 10 次重置到第 1 頁
        for _ in range(10):
            if self._stop.is_set():
                return
            self.click(*LEFT_ARROW, delay=0.15)
        # 再點右箭頭到達目標頁
        for _ in range(target_page - 1):
            if self._stop.is_set():
                return
            self.click(*RIGHT_ARROW, delay=0.15)
        time.sleep(0.3)

    def setup_stove(self, sx, sy, page, dish):
        # 第一步：點鍋爐開食譜
        self.click(sx, sy, delay=1.0)
        if self._stop.is_set():
            return
        # 翻到目標頁
        self.navigate_to_page(page)
        if self._stop.is_set():
            return
        # 點選菜色
        dx, dy = DISH_POS[dish - 1]
        self.click(dx, dy, delay=0.5)
        # 關閉食譜
        self.click(*RECIPE_CLOSE, delay=0.5)
        # 第二步：再點鍋爐開始倒數
        self.click(sx, sy, delay=0.5)

    def run(self, page, dish, cook_minutes, restart_delay, on_status):
        self.hwnd = self.find_window()
        if not self.hwnd:
            on_status("找不到 Flash Player 視窗", error=True)
            return

        self._stop.clear()

        while not self._stop.is_set():
            # 設定 6 個鍋爐
            on_status("設定鍋爐中…")
            for sx, sy in STOVES:
                if self._stop.is_set():
                    break
                self.setup_stove(sx, sy, page, dish)
                if not self.wait(0.8):
                    break

            if self._stop.is_set():
                break

            # 等待烹飪完成
            on_status(f"等待 {cook_minutes} 分鐘…")
            if not self.wait(cook_minutes * 60):
                break

            # 收菜
            on_status("收菜中…")
            for sx, sy in STOVES:
                if self._stop.is_set():
                    break
                self.click(sx, sy, delay=0.8)

            if self._stop.is_set():
                break

            # 重新開始前等待
            on_status(f"等待 {restart_delay} 秒後重新開始…")
            if not self.wait(restart_delay):
                break

        on_status("已停止")

    def stop(self):
        self._stop.set()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("摩爾莊園｜餐廳自動做菜")
        self.root.resizable(False, False)
        self.bot = RestaurantBot()
        self.thread = None
        self._build_ui()

    def _build_ui(self):
        f = ttk.Frame(self.root, padding=15)
        f.pack()

        labels = ["食譜頁數 (1~9)", "菜的位置 (1~6)", "烹飪時間（分鐘）", "收菜後延遲（秒）"]
        defaults = [6, 1, 20, 30]
        ranges = [(1, 9), (1, 6), (1, 99), (0, 600)]
        self.vars = []

        for i, (lbl, val, (lo, hi)) in enumerate(zip(labels, defaults, ranges)):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky=tk.W, pady=4, padx=(0, 10))
            v = tk.IntVar(value=val)
            ttk.Spinbox(f, from_=lo, to=hi, textvariable=v, width=8).grid(row=i, column=1, pady=4)
            self.vars.append(v)

        self.status = ttk.Label(f, text="狀態：待機", foreground="gray")
        self.status.grid(row=len(labels), column=0, columnspan=2, pady=(12, 6))

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=len(labels)+1, column=0, columnspan=2)

        self.start_btn = ttk.Button(btn_frame, text="開始", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=6)

        self.stop_btn = ttk.Button(btn_frame, text="停止", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=6)

    def _start(self):
        page, dish, minutes, delay = [v.get() for v in self.vars]
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.thread = threading.Thread(
            target=self.bot.run,
            args=(page, dish, minutes, delay, self._on_status),
            daemon=True
        )
        self.thread.start()

    def _stop(self):
        self.bot.stop()
        self.stop_btn.config(state=tk.DISABLED)

    def _on_status(self, msg, error=False):
        color = "red" if error else ("gray" if msg == "已停止" else "green")
        self.root.after(0, lambda: self.status.config(text=f"狀態：{msg}", foreground=color))
        if msg == "已停止" or error:
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        if error:
            self.root.after(0, lambda: messagebox.showerror("錯誤", msg))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

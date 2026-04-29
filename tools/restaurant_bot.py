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
        "confirm_btn": tuple(r.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])),
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

        check   = self.recipe["check_pt"]
        dish_pt = self.recipe["dishes"][dish - 1]

        # 步驟 1：點鍋爐，偵測食譜開啟（最多 2 次，處理鍋爐上有菜的情況）
        confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        recipe_opened = False
        for attempt in range(3):
            if self._stop.is_set(): return
            log(f"點鍋爐 ({sx},{sy})…" + (f"（第 {attempt+1} 次）" if attempt else ""))
            pre = self.get_pixel(*check)
            self.click(sx, sy, delay=0.3)
            ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)
            if ok:
                log(f"食譜已開啟 ✓ ({c_before}→{c_after})")
                recipe_opened = True
                break
            # 食譜沒開：可能是收菜動畫、做菜中、或腐壞彈窗
            # 點確認清除（腐壞情況），或等動畫結束後重試
            log(f"未偵測到食譜，點確認 ({confirm_btn[0]},{confirm_btn[1]}) 清除可能的腐壞/彈窗…")
            self.click_real(*confirm_btn, delay=1.0)

        if not recipe_opened:
            log(f"鍋爐 ({sx},{sy}) 3 次後仍無法開啟食譜（可能正在做菜），跳過")
            return
        if self._stop.is_set(): return

        # 步驟 2：切換頁面
        log(f"切換到第 {page} 頁…")
        self.navigate_to_page(page)
        if self._stop.is_set(): return

        # 步驟 3：點菜色
        log(f"點菜色 {dish}，座標 ({dish_pt[0]},{dish_pt[1]})…")
        pre = self.get_pixel(*check)
        self.click_real(*dish_pt, delay=0.3)
        ok, c_before, c_after = self.wait_for_pixel_change(*check, timeout=3.0, baseline=pre)
        if ok:
            log(f"烹飪開始 ✓ ({c_before}→{c_after})")
        else:
            log(f"點菜偵測無變化（{c_before}），若食譜還開著請重新校準菜格座標")

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

        self.start_btn  = ttk.Button(btn_f, text="開始",     command=self._start)
        self.stop_btn   = ttk.Button(btn_f, text="停止",     command=self._stop, state=tk.DISABLED)
        self.calib_s    = ttk.Button(btn_f, text="校準鍋爐", command=self._calib_stoves)
        self.calib_r    = ttk.Button(btn_f, text="校準食譜", command=self._calib_recipe)
        self.calib_c    = ttk.Button(btn_f, text="校準確認鈕", command=self._calib_cancel)
        self.preview_btn= ttk.Button(btn_f, text="預覽座標", command=self._preview_coords)

        for btn in (self.start_btn, self.stop_btn, self.calib_s, self.calib_r, self.calib_c, self.preview_btn):
            btn.pack(side=tk.LEFT, padx=4)

    def _get_settings(self):
        return {k: v.get() for k, v in self.vars.items()}

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        self.start_btn.config(state=sa)
        self.calib_s.config(state=sa)
        self.calib_r.config(state=sa)
        self.calib_c.config(state=sa)
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
            "校準確認按鈕",
            "請先點有腐壞食物的鍋爐，讓「捐菜給拉姆」彈窗出現，\n再回到這裡點「確定」開始校準。\n\n截圖後點一下彈窗的「確認」按鈕位置。"
        )
        CalibrationWindow(self.root, hwnd, ["確認按鈕"], self._done_cancel)

    def _done_cancel(self, pts):
        self.recipe["confirm_btn"] = pts[0]
        self.bot.recipe = self.recipe
        self._save_all()
        messagebox.showinfo("完成", f"確認按鈕座標已儲存：{pts[0]}")

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

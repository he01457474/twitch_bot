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

        # 先收集三種狀態的命中結果，最後用 best-match 決定
        hit_sp, diff_sp, (spx, spy) = check_state("spoiled_points", "spoiled_color", "spoiled_offset", spread=6)
        markers.append((spx, spy, "red", f"spoiled Δ{diff_sp}"))

        hit_d, diff_d, (dx, dy) = check_state("done_points", "done_color", "done_offset")
        markers.append((dx, dy, "yellow", f"done Δ{diff_d}"))

        # 時鐘 → 烹飪中（動畫，時序重試）
        clock_calibrated = bool(
            self.settings.get("clock_points") or self.settings.get("clock_color")
        )
        clock_hit, clock_diff, clock_pt = False, 999, (sx, sy)
        if clock_calibrated:
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

        # 建立候選集，選出最佳匹配
        candidates = {}
        if hit_sp:   candidates["spoiled"] = diff_sp
        if hit_d:    candidates["done"]    = diff_d
        if clock_hit: candidates["cooking"] = clock_diff

        if not candidates:
            return "unknown"

        # cooking 和 spoiled 同時命中時，優先採用 cooking：
        # 烹飪動畫偶爾觸發 spoiled 閾值，但此時 cooking 也必定命中，
        # 誤清除正在烹飪的食物的代價遠大於漏掉一次腐壞偵測。
        if "cooking" in candidates and "spoiled" in candidates:
            self._debug_capture(f"cooking_beats_spoiled_{sx}_{sy}", markers)
            return "cooking"

        best = min(candidates, key=candidates.get)
        if best in ("spoiled", "done"):
            self._debug_capture(f"{best}_{sx}_{sy}", markers)
        return best

    def is_stove_spoiled(self, sx, sy):
        return self.detect_stove_state(sx, sy) == "spoiled"

    def _detect_safe(self, sx, sy):
        """
        嚴謹版狀態偵測：連偵測兩次（間隔 0.3 秒），採保守判斷。
        任一次偵測到 cooking 或 spoiled，即回傳該結果，
        防止烹飪中或腐壞的鍋爐被誤判為 unknown 而浪費食材。
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
        # spoiled 需兩次都確認，避免烹飪動畫觸發偶發假陽性後就直接清除食材
        if s1 == "spoiled" and s2 == "spoiled":
            return "spoiled"
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
        return self.color_diff(current, tuple(color)) < threshold

    def is_recipe_open(self):
        """根據 check_pt 和記錄的關閉基準色，判斷食譜是否開著"""
        if self._recipe_closed_baseline is None:
            return False
        current = self.get_pixel(*self.recipe["check_pt"])
        threshold = self.settings.get("state_threshold", 40)
        return self.color_diff(current, tuple(self._recipe_closed_baseline)) > threshold

    # ── 鍋爐動作：收菜 / 清除腐壞 / 做菜步驟 ────────────

    def _collect_food(self, sx, sy, log):
        """收菜（食物做好時點鍋爐）"""
        log("收菜…")
        self.click(sx, sy, delay=0.5)
        self.wait(1.5)

    def _clear_spoiled(self, sx, sy, log):
        """
        清除腐壞食物。最多試 2 次，成功回傳 True。
        流程：確認腐壞 → 點鍋爐 → 等彈窗 → 點確認 → 確認是否清除成功。
        點確認前會先偵測有沒有意外開食譜，避免 confirm_btn 座標點到食譜菜色。
        """
        confirm_btn = self.recipe.get("confirm_btn", DEFAULT_RECIPE["confirm_btn"])
        close_btn   = self.recipe.get("close",       DEFAULT_RECIPE["close"])
        for _try in range(2):
            # 點確認前再確認一次腐壞狀態，偵測失準時不誤按
            time.sleep(0.2)
            if self.detect_stove_state(sx, sy) != "spoiled":
                log("腐壞狀態已消失，不需清除")
                return True
            log("腐壞確認，清除…")
            self.click(sx, sy, delay=0.5)
            self.wait(0.8)
            # 若意外開了食譜（stove 實際非腐壞），先關掉食譜再跳過
            # 避免 confirm_btn 座標誤點到食譜裡的菜色
            if self.is_recipe_open():
                log("意外開啟食譜（非腐壞彈窗），關閉並跳過")
                self.click_real(*close_btn, delay=0.5)
                return False
            self.click_real(*confirm_btn, delay=0.5)
            if self._stop.is_set(): return False
            self.wait(1.5)
            if self.detect_stove_state(sx, sy) != "spoiled":
                return True
            log("清除後仍偵測到腐壞，重試…")
        return False

    def _do_steps(self, sx, sy, log):
        """
        執行最多 3 個烹飪步驟（製作餐具、放食材、開始烹飪）。

        每步點完觀察反應：
          有讀條 → 等結束 → 繼續下一步
          已烹飪 → 直接結束
          無讀條 → 點取消關掉可能的彈窗，結束（讓下輪重試，不跑防卡頓）
        """
        cancel_btn = self.recipe.get("cancel_btn", DEFAULT_RECIPE["cancel_btn"])
        labels = ["製作餐具", "放食材", "開始烹飪"]

        for step in range(3):
            if self._stop.is_set(): return

            # 前兩步（製作餐具、放食材）用嚴謹雙重偵測，
            # 確保不在烹飪中才繼續，避免誤操作浪費食材
            state = self._detect_safe(sx, sy) if step <= 1 else self.detect_stove_state(sx, sy)
            if state in ("cooking", "done"):
                log("已進入烹飪 ✓")
                return
            if state == "spoiled":
                log("偵測到腐壞，停止")
                return

            log(f"{labels[step]}…")
            pre = self.get_pixel(sx, sy)
            self.click(sx, sy, delay=0.2)

            # 等讀條出現（最多 2 秒）
            bar_ok, _, bar_color = self.wait_for_pixel_change(
                sx, sy, timeout=2.0, baseline=pre)

            if not bar_ok:
                # 沒讀條，再確認一次狀態
                state = self.detect_stove_state(sx, sy)
                if state in ("cooking", "done"):
                    log("已進入烹飪 ✓")
                    return
                # 可能有彈窗，點取消保底，等下輪處理
                log(f"{labels[step]}：無讀條，關彈窗等下輪")
                self._debug_capture(f"no_bar_{sx}_{sy}_step{step+1}")
                self.click_real(*cancel_btn, delay=0.5)
                return

            # 讀條出現，排除腐壞誤觸
            if self.detect_stove_state(sx, sy) == "spoiled":
                log("腐壞誤觸，停止")
                return

            log(f"{labels[step]}：讀條中…")

            # 等讀條結束（最多 20 秒），偵測到烹飪就立刻離開
            deadline = time.time() + 20.0
            while time.time() < deadline and not self._stop.is_set():
                state = self.detect_stove_state(sx, sy)
                if state in ("cooking", "done"):
                    log("已進入烹飪 ✓")
                    return
                if state == "spoiled":
                    return
                if self.color_diff(self.get_pixel(sx, sy), bar_color) > 40:
                    break   # 讀條結束，繼續下一步
                time.sleep(0.2)

            time.sleep(0.3)   # 步驟間緩衝

    def _open_recipe_and_cook(self, sx, sy, page, dish, log):
        """
        點鍋爐開食譜 → 選菜 → 做步驟。

        若食譜沒開，觀察其他反應：
          - 已在讀條中 → 等結束再接續步驟
          - 狀態改變（烹飪/完成/腐壞）→ 對應處理
          - 完全無反應 → 點取消保底，跳過
        兩次都失敗直接跳過（不跑防卡頓）。
        """
        check      = self.recipe["check_pt"]
        cancel_btn = self.recipe.get("cancel_btn", DEFAULT_RECIPE["cancel_btn"])
        threshold  = self.settings.get("state_threshold", 40)

        # 食譜已開著（例如上輪未關），直接選菜
        if self.is_recipe_open():
            log("食譜已開著，直接選菜…")
            if self._select_dish(page, dish, check, log):
                self.wait(0.8)
                self._do_steps(sx, sy, log)
            return

        for attempt in range(2):
            if self._stop.is_set(): return

            pre_check = self.get_pixel(*check)
            pre_stove = self.get_pixel(sx, sy)
            self.click(sx, sy, delay=0.3)

            # 等食譜開啟（1.5 秒）
            recipe_ok, _, _ = self.wait_for_pixel_change(
                *check, timeout=1.5, baseline=pre_check)

            if recipe_ok:
                log("食譜已開啟 ✓")
                if self._select_dish(page, dish, check, log):
                    self.wait(0.8)
                    self._do_steps(sx, sy, log)
                return

            # 食譜沒開，用嚴謹偵測確認狀態，避免誤把烹飪中當作 unknown
            state = self._detect_safe(sx, sy)
            if state == "cooking":
                log("烹飪中（之前未偵測到），跳過")
                return
            if state == "done":
                log("食物做好（之前未偵測到），收菜")
                self._collect_food(sx, sy, log)
                return
            if state == "spoiled":
                log("腐壞（之前未偵測到），清除")
                self._clear_spoiled(sx, sy, log)
                return

            # 鍋爐像素有沒有持續變化（已在讀條中）
            stove_now = self.get_pixel(sx, sy)
            if self.color_diff(stove_now, pre_stove) > threshold:
                time.sleep(0.4)
                if self.color_diff(self.get_pixel(sx, sy), pre_stove) > threshold:
                    log("偵測到讀條（中間步驟），等結束…")
                    self.wait_for_pixel_change(sx, sy, timeout=15.0, baseline=stove_now)
                    self.wait(0.5)
                    state = self.detect_stove_state(sx, sy)
                    if state not in ("cooking", "done"):
                        self._do_steps(sx, sy, log)
                    return

            # 完全無反應，點取消關掉可能的彈窗
            log(f"無反應（第 {attempt+1} 次），關彈窗…")
            self.click_real(*cancel_btn, delay=0.5)

        log(f"鍋爐 ({sx},{sy}) 兩次都無法開食譜，跳過")

    def setup_stove(self, sx, sy, page, dish, on_status=None):
        """
        處理單個鍋爐，流程：
          1. 偵測狀態
          2. cooking → 跳過
             done    → 收菜
             spoiled → 清除（失敗就跳過）
             unknown → 直接嘗試開始做菜
          3. 做菜（開食譜 → 選菜 → 三步驟）

        遇到問題只跳過，不跑 leave_and_return。
        """
        def log(msg):
            if on_status: on_status(msg)

        state = self._detect_safe(sx, sy)
        log(f"鍋爐 ({sx},{sy})：{state}")

        if state == "cooking":
            return

        if state == "done":
            self._collect_food(sx, sy, log)
            state = self._detect_safe(sx, sy)
            if state not in ("unknown",):
                return   # 還有東西，下輪再處理

        if state == "spoiled":
            if not self._clear_spoiled(sx, sy, log):
                log("清除失敗，跳過")
                return
            state = self._detect_safe(sx, sy)
            if state == "done":
                self._collect_food(sx, sy, log)
            elif state not in ("unknown",):
                return

        # 空鍋爐，開始做菜
        self._open_recipe_and_cook(sx, sy, page, dish, log)

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
            elapsed += 1.0
            # 以 _last_antlag 判斷，和掃描前的防卡頓共用同一個計時器，不會重複觸發
            if (interval_seconds > 0 and elapsed < total_seconds and
                    time.time() - self._last_antlag >= interval_seconds):
                self.leave_and_return(on_status)
                if not self._is_in_restaurant():
                    on_status("防卡頓後未偵測到餐廳，30 秒後重試…")
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
            # 掃描前防卡頓：若距上次防卡頓已超過設定間隔，先出去繞一圈再掃
            # 這樣即使掃描本身耗時，Flash Player 也不會在掃描前就已經積累太久
            if antlag_sec > 0 and time.time() - self._last_antlag >= antlag_sec:
                on_status("掃描前防卡頓…")
                self.leave_and_return(on_status)
                if self._stop.is_set(): break

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
            self.save_live_snapshot("掃描前")   # 存桌面快照供除錯
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

        # ── 校準 ─────────────────────────────────────────
        grp_cal = ttk.LabelFrame(f, text="校準", padding=(10, 4))
        grp_cal.pack(fill=tk.X, pady=(0, 6))

        row_c = ttk.Frame(grp_cal)
        row_c.pack(fill=tk.X, pady=(2, 0))
        self.calib_s    = ttk.Button(row_c, text="鍋爐",   command=self._calib_stoves)
        self.calib_r    = ttk.Button(row_c, text="食譜",   command=self._calib_recipe)
        self.calib_c    = ttk.Button(row_c, text="彈窗",   command=self._calib_cancel)
        self.calib_sp   = ttk.Button(row_c, text="狀態色", command=self._calib_state_colors)
        self.calib_door = ttk.Button(row_c, text="門口",   command=self._calib_door)
        self.calib_rest = ttk.Button(row_c, text="餐廳",   command=self._calib_restaurant)
        for btn in (self.calib_s, self.calib_r, self.calib_c,
                    self.calib_sp, self.calib_door, self.calib_rest):
            btn.pack(side=tk.LEFT, padx=3)

        # 校準狀態指示列
        self._calib_lbl = {}
        row_cs = ttk.Frame(grp_cal)
        row_cs.pack(fill=tk.X, pady=(2, 4))
        for key, title in (("stoves", "鍋爐"), ("recipe", "食譜"), ("cancel", "彈窗"),
                            ("state",  "狀態色"), ("door",  "門口"), ("restaurant", "餐廳")):
            lbl = ttk.Label(row_cs, text=f"▸{title}", font=("", 8))
            lbl.pack(side=tk.LEFT, padx=(4, 10))
            self._calib_lbl[key] = lbl
        self._refresh_calib_status()

        # ── 狀態 ─────────────────────────────────────────
        self.status = ttk.Label(f, text="狀態：待機", foreground="gray",
                                font=("", 10, "bold"), anchor=tk.W)
        self.status.pack(fill=tk.X, pady=(2, 6))

        # ── 執行 ─────────────────────────────────────────
        grp_run = ttk.LabelFrame(f, text="執行", padding=(10, 4))
        grp_run.pack(fill=tk.X, pady=(0, 6))
        self.start_btn = ttk.Button(grp_run, text="▶ 開始", command=self._start, width=10)
        self.stop_btn  = ttk.Button(grp_run, text="■ 停止", command=self._stop,  width=10,
                                    state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6), pady=4)
        self.stop_btn.pack(side=tk.LEFT, pady=4)

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
        for btn in (self.testdet_btn, self.preview_btn, self.snap_btn,
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
            "state":      bool(s.get("done_points") or s.get("clock_points") or
                               s.get("spoiled_points") or s.get("done_color") or
                               s.get("clock_color") or s.get("spoiled_color")),
            "door":       bool(s.get("door_out") and s.get("door_in")),
            "restaurant": bool(s.get("restaurant_pt") and s.get("restaurant_color")),
        }
        titles = {"stoves": "鍋爐", "recipe": "食譜", "cancel": "彈窗",
                  "state": "狀態色", "door": "門口", "restaurant": "餐廳"}
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

    def _get_settings(self):
        s = {k: v.get() for k, v in self.vars.items()}
        s.update(self._extra_settings)  # 合併 spoiled_color / spoiled_threshold
        return s

    def _set_running(self, running):
        sa = tk.DISABLED if running else tk.NORMAL
        sb = tk.NORMAL   if running else tk.DISABLED
        for btn in (self.start_btn, self.calib_s, self.calib_r,
                    self.calib_c, self.calib_sp, self.calib_door, self.calib_rest,
                    self.testnav_btn, self.testdet_btn, self.preview_btn, self.snap_btn):
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
        self._refresh_calib_status()
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
            self._save_all()
            self._refresh_calib_status()
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
            n_stoves = len(self.stoves)
            if points:
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
        個別校準：依序點擊 N 個鍋爐各自的偵測位置（一格一點）。
        儲存為 <state>_points 格式 [[dx,dy,r,g,b], ...]，元素數量等於鍋爐數。
        偵測時每個鍋爐只取自己那個點，不會互相干擾。
        """
        state_name = color_key.replace("_color", "")   # done / clock / spoiled
        points_key = f"{state_name}_points"
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

        sg         = max(game_w / MOLE_W, game_h / MOLE_H)
        disp_scale = min(900 / game_w, 580 / game_h, 1.0)
        img_rgb = img.convert("RGB")
        disp    = img.resize((int(game_w * disp_scale), int(game_h * disp_scale)))
        photo   = ImageTk.PhotoImage(disp)

        point_hints = {
            "clock_offset":   "橙色時鐘圓圈",
            "done_offset":    "食物做好的黃光",
            "spoiled_offset": "鍋爐上方的黑煙",
        }
        pt_hint = point_hints.get(offset_key, label)

        win = tk.Toplevel(self.root)
        win.title(f"校準「{label}」（各鍋爐獨立）")
        win.grab_set()

        instr_lbl = ttk.Label(win, text="", padding=8, font=("", 11, "bold"))
        instr_lbl.pack()
        sub_lbl = ttk.Label(win,
            text=f"點擊對應鍋爐的「{pt_hint}」位置。按「上一步」可撤回，按「重新來過」清空全部。",
            foreground="gray", padding=(8, 0, 8, 4), wraplength=600)
        sub_lbl.pack()

        canvas = tk.Canvas(win,
                           width=int(game_w * disp_scale),
                           height=int(game_h * disp_scale),
                           cursor="crosshair")
        canvas.pack(padx=8, pady=4)
        canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        canvas.photo = photo

        # ── 鍋爐位置標記（空心圓 + 序號） ──
        stove_ovals = []   # (oval_id, text_id) per stove
        for i, (sx, sy) in enumerate(self.stoves):
            ex = int(sx * sg * disp_scale)
            ey = int(sy * sg * disp_scale)
            ov = canvas.create_oval(ex-14, ey-14, ex+14, ey+14,
                                    outline="gray", width=2)
            tx = canvas.create_text(ex, ey, text=str(i+1),
                                    fill="gray", font=("Arial", 10, "bold"))
            stove_ovals.append((ov, tx))

        collected   = []    # [[dx,dy,r,g,b], ...]
        dot_canvas_items = []   # (dot_id, lbl_id) 已畫的偵測點

        def refresh_ui():
            idx = len(collected)
            if idx < n:
                instr_lbl.config(
                    text=f"第 {idx+1} / {n} 個鍋爐　→　請點鍋爐 {idx+1} 的偵測位置",
                    foreground="black")
                for i, (ov, tx) in enumerate(stove_ovals):
                    if i < idx:
                        col = "#27ae60"    # 已完成：深綠
                    elif i == idx:
                        col = "green"      # 目前目標：亮綠
                    else:
                        col = "gray"       # 未到：灰
                    canvas.itemconfig(ov, outline=col, width=3 if i == idx else 2)
                    canvas.itemconfig(tx, fill=col)
            else:
                instr_lbl.config(
                    text=f"全部 {n} 個鍋爐校準完成！按「儲存」確認。",
                    foreground="#27ae60")
                for ov, tx in stove_ovals:
                    canvas.itemconfig(ov, outline="#27ae60", width=2)
                    canvas.itemconfig(tx, fill="#27ae60")

        refresh_ui()

        def on_pick(event):
            idx = len(collected)
            if idx >= n:
                return
            px  = min(int(event.x / disp_scale), game_w - 1)
            py  = min(int(event.y / disp_scale), game_h - 1)
            mx  = int(px / sg)
            my  = int(py / sg)
            rgb = img_rgb.getpixel((px, py))
            sx, sy = self.stoves[idx]
            dx, dy = mx - sx, my - sy
            collected.append([dx, dy, rgb[0], rgb[1], rgb[2]])
            # 畫偵測點（小實心圓）
            r = 6
            d = canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r,
                                   fill="lime", outline="green", width=2)
            t = canvas.create_text(event.x + 12, event.y, text=str(idx+1),
                                   fill="green", font=("Arial", 9, "bold"))
            dot_canvas_items.append((d, t))
            refresh_ui()

        def on_undo():
            if not collected:
                return
            collected.pop()
            if dot_canvas_items:
                d, t = dot_canvas_items.pop()
                canvas.delete(d)
                canvas.delete(t)
            refresh_ui()

        def on_clear():
            collected.clear()
            for d, t in dot_canvas_items:
                canvas.delete(d)
                canvas.delete(t)
            dot_canvas_items.clear()
            self._extra_settings[points_key] = []
            self.bot.settings[points_key]    = []
            self._save_all()
            refresh_ui()

        def on_save():
            if len(collected) < n:
                messagebox.showwarning("提示",
                    f"還差 {n - len(collected)} 個鍋爐沒校準。")
                return
            self._extra_settings[points_key] = collected[:]
            self.bot.settings[points_key]    = collected[:]
            # 清除舊格式（改用個別 points，舊格式已無作用）
            for k in (color_key, offset_key):
                if k:
                    self._extra_settings[k] = None
                    self.bot.settings[k]    = None
            self._save_all()
            self._refresh_calib_status()
            win.destroy()
            messagebox.showinfo("完成",
                f"「{label}」已儲存 {n} 個個別校準點。\n"
                "每個鍋爐只用自己那個點偵測，不互相干擾。")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)
        ttk.Button(btn_frame, text="儲存",      command=on_save ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="上一步",    command=on_undo ).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="重新來過",  command=on_clear).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="取消",      command=win.destroy).pack(side=tk.LEFT, padx=6)

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
        self._save_all()
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

        ttk.Label(win, text="每 0.5 秒掃一次所有鍋爐，Δ 值越小代表越接近校準顏色，< threshold 表示偵測到。",
                  padding=(10, 8, 10, 4), wraplength=480).pack()

        threshold = self.bot.settings.get("state_threshold", 40)
        ttk.Label(win, text=f"目前 threshold = {threshold}（校準狀態色介面可調整）",
                  foreground="gray", padding=(10, 0, 10, 6)).pack()

        frame = ttk.Frame(win, padding=8)
        frame.pack(fill=tk.BOTH)

        # 表頭
        headers = ["鍋爐", "座標", "狀態", "做完 Δ", "時鐘 Δ", "腐壞 Δ"]
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

                def best_delta(pts_key, color_key, off_key, spread, _sx, _sy, _idx):
                    pts   = s.get(pts_key) or []
                    color = s.get(color_key)
                    off   = s.get(off_key) or [0, 0]
                    if not pts and not color:
                        return "未校準"
                    best = 999
                    if pts:
                        # 個別校準模式：只看這個鍋爐自己的點
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

                for i, (sx, sy) in enumerate(self.bot.stoves):
                    if stop_event.is_set():
                        break

                    # 偵測狀態（用同一張截圖，不重新截圖）
                    state = self.bot.detect_stove_state(sx, sy)

                    done_d    = best_delta("done_points",    "done_color",    "done_offset",    4, sx, sy, i)
                    clock_d   = best_delta("clock_points",   "clock_color",   "clock_offset",   4, sx, sy, i)
                    spoiled_d = best_delta("spoiled_points", "spoiled_color", "spoiled_offset", 6, sx, sy, i)

                    sc = {"cooking": "blue", "done": "orange",
                          "spoiled": "red",  "unknown": "gray"}.get(state, "gray")

                    def update_row(idx=i, st=state, fg=sc,
                                   dd=done_d, cd=clock_d, sd=spoiled_d):
                        if not win.winfo_exists():
                            return
                        row_labels[idx][0].config(text=str(idx+1))
                        row_labels[idx][1].config(text=str(self.bot.stoves[idx]))
                        row_labels[idx][2].config(text=st, foreground=fg)
                        row_labels[idx][3].config(text=dd)
                        row_labels[idx][4].config(text=cd)
                        row_labels[idx][5].config(text=sd)

                    win.after(0, update_row)

                time.sleep(0.8)   # 背景執行緒等待，不佔用 UI

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


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()

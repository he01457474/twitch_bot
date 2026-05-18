#!/usr/bin/env python3
"""大俠選邊站輔助 - 黃易群俠傳之風起雙龍 O/X 問答顯示工具"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
import sys
import ctypes
import io
import subprocess
from difflib import SequenceMatcher
import win32gui
import win32ui
from PIL import Image, ImageTk

try:
    hwnd_con = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd_con:
        ctypes.windll.user32.ShowWindow(hwnd_con, 0)
except Exception:
    pass

if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE  = os.path.join(_APP_DIR, "sidestand_database.json")
CFG_FILE = os.path.join(_APP_DIR, "sidestand_config.json")

GAME_TITLE_KEYWORDS = ["黃易", "雙龍", "風起", "群俠"]

DEFAULT_CONFIG = {
    "popup_check_x": 0.45,
    "popup_check_y": 0.10,
    "popup_brightness_threshold": 80,
    "question_region": {
        "left": 0.17, "top": 0.12,
        "right": 0.74, "bottom": 0.27,
    },
    "popup_full_region": {
        "left": 0.15, "top": 0.09,
        "right": 0.76, "bottom": 0.30,
    },
    "api_key": "",
    "match_threshold": 0.72,
}

_OCR_SCRIPT = r"""
import sys, asyncio
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
    for tag in ['zh-TW', 'zh-Hans-CN']:
        lang = glob.Language(tag)
        if ocr.OcrEngine.is_language_supported(lang):
            engine = ocr.OcrEngine.try_create_from_language(lang)
            if engine:
                result = await engine.recognize_async(bitmap)
                print(result.text if result else '', end='')
                return

asyncio.run(run())
"""


# ── 截圖 ──────────────────────────────────────────────────────────────────────

def capture_window(hwnd):
    rect   = win32gui.GetClientRect(hwnd)
    w, h   = rect[2], rect[3]
    hwndDC = win32gui.GetDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    bmp    = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), 0x00CC0020)
    bmpinfo = bmp.GetInfo()
    bmpdata = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                           bmpdata, "raw", "BGRX", 0, 1)
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    win32gui.DeleteObject(bmp.GetHandle())
    return img, w, h


# ── Perceptual Hash ───────────────────────────────────────────────────────────

def compute_phash(img):
    small = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / 64
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits

def phash_distance(a, b):
    x = a ^ b
    count = 0
    while x:
        count += x & 1
        x >>= 1
    return count


# ── OCR ───────────────────────────────────────────────────────────────────────

def ocr_image(pil_img):
    try:
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        proc = subprocess.run(
            [sys.executable, "-c", _OCR_SCRIPT],
            input=buf.getvalue(), capture_output=True, timeout=10,
        )
        return proc.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


# ── Claude API ────────────────────────────────────────────────────────────────

def claude_read_question(pil_img, api_key):
    """用 Claude API 讀出題目文字（O/X 問答只需要題目，不需要選項）。"""
    try:
        import anthropic, base64
        buf = io.BytesIO()
        img = pil_img.convert("RGB")
        if max(img.width, img.height) < 600:
            scale = max(2, 600 // max(img.width, img.height))
            img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "這是一個武俠遊戲的問答截圖（繁體中文）。請只輸出題目文字，不要任何選項、說明或標點符號以外的內容。"},
            ]}],
        )
        return resp.content[0].text.strip()
    except Exception:
        return ""


# ── 題庫 ──────────────────────────────────────────────────────────────────────

class SidestandDatabase:
    def __init__(self, path):
        self.path    = path
        self.entries = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = []

    def lookup(self, question, threshold=0.72):
        """模糊比對，回傳最佳匹配的 entry（含 similarity）或 None。"""
        best_entry = None
        best_score = 0.0
        for e in self.entries:
            score = SequenceMatcher(None, question, e["question"]).ratio()
            if score > best_score:
                best_score = score
                best_entry = e
        if best_entry and best_score >= threshold:
            return dict(best_entry, similarity=round(best_score, 3))
        return None

    def add(self, question, answer):
        self.entries.append({"question": question, "answer": answer})
        self._save()

    def delete(self, idx):
        if 0 <= idx < len(self.entries):
            self.entries.pop(idx)
            self._save()

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)


# ── 偵測器 ────────────────────────────────────────────────────────────────────

class SidestandDetector:
    def __init__(self, config, db):
        self.config   = config
        self.db       = db
        self._stop    = threading.Event()
        self._popup_on = False
        self._last_ph  = None

    def find_window(self):
        result = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            t = win32gui.GetWindowText(hwnd)
            if any(k in t for k in GAME_TITLE_KEYWORDS):
                result.append((hwnd, t))
        win32gui.EnumWindows(cb, None)
        return result[0] if result else None

    def _crop(self, img, w, h, region_key):
        r  = self.config.get(region_key, {})
        x1 = int(r.get("left",   0) * w)
        y1 = int(r.get("top",    0) * h)
        x2 = int(r.get("right",  1) * w)
        y2 = int(r.get("bottom", 1) * h)
        return img.crop((x1, y1, x2, y2))

    def sample_brightness(self, img, w, h):
        cx = int(self.config.get("popup_check_x", 0.45) * w)
        cy = int(self.config.get("popup_check_y", 0.10) * h)
        r  = 6
        region = img.crop((max(0, cx-r), max(0, cy-r),
                           min(w, cx+r), min(h, cy+r)))
        pixels = list(region.getdata())
        if not pixels:
            return 255
        return sum(sum(p) for p in pixels) / (len(pixels) * 3)

    def process_frame(self, img, w, h, on_status):
        visible = self.sample_brightness(img, w, h) < self.config.get(
            "popup_brightness_threshold", 80)

        if not visible:
            if self._popup_on:
                self._popup_on = False
                self._last_ph  = None
                on_status("等待題目…")
            return None

        if not self._popup_on:
            self._popup_on = True

        q_img = self._crop(img, w, h, "question_region")
        ph    = compute_phash(q_img)

        if ph == 0 or ph == (1 << 64) - 1:
            return None

        if self._last_ph is not None and phash_distance(ph, self._last_ph) < 4:
            return None

        self._last_ph = ph
        on_status("偵測到題目，查詢題庫…")

        # 辨識題目文字
        api_key = self.config.get("api_key", "").strip()
        q_text  = ""

        if api_key:
            on_status("Claude API 辨識中…")
            full_img = self._crop(img, w, h, "popup_full_region")
            q_text   = claude_read_question(full_img, api_key)
            if not q_text:
                on_status("API 辨識失敗，改用 OCR…")

        if not q_text:
            q_text = ocr_image(q_img)

        if not q_text:
            on_status("辨識失敗，請確認視窗是否在前景")
            return None

        # 題庫比對
        threshold = self.config.get("match_threshold", 0.72)
        entry = self.db.lookup(q_text, threshold)
        if entry:
            on_status(f"命中（相似度 {entry['similarity']:.0%}）")
            return dict(entry, phash=ph, recognized=q_text)

        on_status(f"題庫未找到：{q_text[:20]}…")
        return {"question": q_text, "answer": None, "phash": ph, "recognized": q_text}

    def run(self, on_result, on_status, on_error, on_popup_gone=None):
        self._stop.clear()
        found = self.find_window()
        if not found:
            on_error("找不到遊戲視窗，請確認遊戲已開啟")
            return
        self.hwnd, title = found
        on_status(f"已連接：{title}")
        while not self._stop.is_set():
            try:
                if not (win32gui.IsWindow(self.hwnd) and
                        win32gui.IsWindowVisible(self.hwnd)):
                    on_error("遊戲視窗已關閉")
                    return
                img, w, h  = capture_window(self.hwnd)
                was_on     = self._popup_on
                result     = self.process_frame(img, w, h, on_status)
                if result:
                    on_result(result)
                if was_on and not self._popup_on and on_popup_gone:
                    on_popup_gone()
            except Exception as e:
                on_status(f"錯誤：{e}")
            self._stop.wait(0.5)

    def stop(self):
        self._stop.set()


# ── GUI ───────────────────────────────────────────────────────────────────────

BG       = "#0F0F1A"
BG2      = "#1A1A2E"
ACCENT   = "#E94560"
TEXT_DIM = "#888888"
TEXT_NORM = "#CCCCCC"
COL_O    = "#2ECC71"   # 綠色 = O（正確）
COL_X    = "#E74C3C"   # 紅色 = X（錯誤）
COL_UNK  = "#555577"   # 灰色 = 未知


class SidestandApp:
    def __init__(self, root):
        self.root    = root
        self.root.title("大俠選邊站輔助")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.config   = self._load_config()
        self.db       = SidestandDatabase(DB_FILE)
        self.detector = SidestandDetector(self.config, self.db)
        self._thread  = None
        self._current = None
        self._pinned  = True

        self._build_ui()

    def _load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(CFG_FILE):
            try:
                with open(CFG_FILE, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
            except Exception:
                pass
        return cfg

    def _save_config(self):
        tmp = CFG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, CFG_FILE)

    def _lbl(self, parent, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        return tk.Label(parent, **kw)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG2, foreground=TEXT_NORM, bordercolor=BG)
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_NORM, padding=[8, 4])
        style.map("TNotebook.Tab",       background=[("selected", BG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        f_main = tk.Frame(nb, bg=BG,  padx=8, pady=6)
        f_db   = tk.Frame(nb, bg=BG2)
        f_cfg  = tk.Frame(nb, bg=BG2, padx=10, pady=8)

        nb.add(f_main, text=" 答題 ")
        nb.add(f_db,   text=" 題庫 ")
        nb.add(f_cfg,  text=" 設定 ")

        self._build_main(f_main)
        self._build_db(f_db)
        self._build_cfg(f_cfg)

    def _build_main(self, f):
        # 超大 O / X
        self.ans_var = tk.StringVar(value="─")
        self.ans_lbl = self._lbl(f, textvariable=self.ans_var,
                                 font=("Microsoft JhengHei UI", 120, "bold"),
                                 fg=COL_UNK, bg=BG, pady=0)
        self.ans_lbl.pack(fill=tk.X)

        # 題目文字
        self.q_var = tk.StringVar(value="等待題目出現…")
        self._lbl(f, textvariable=self.q_var,
                  font=("Microsoft JhengHei UI", 11),
                  fg=TEXT_NORM, bg=BG, wraplength=380,
                  justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 2))

        # 相似度 / 來源
        self.source_var = tk.StringVar(value="")
        self._lbl(f, textvariable=self.source_var,
                  font=("Microsoft JhengHei UI", 8),
                  fg=TEXT_DIM, bg=BG).pack(pady=(0, 2))

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # 按鈕列
        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill=tk.X)

        self.start_btn = tk.Button(
            btn_row, text="開始監測",
            font=("Microsoft JhengHei UI", 11),
            bg="#2ECC71", fg="white", activebackground="#27AE60",
            relief=tk.FLAT, padx=14, pady=4,
            command=self._toggle_monitor,
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.save_btn = tk.Button(
            btn_row, text="存入題庫",
            font=("Microsoft JhengHei UI", 11),
            bg="#3498DB", fg="white", activebackground="#2980B9",
            relief=tk.FLAT, padx=14, pady=4,
            command=self._save_to_db, state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.LEFT)

        self.pin_btn = tk.Button(
            btn_row, text="📌",
            font=("Segoe UI Emoji", 13),
            bg="#2C3E50", fg="#F1C40F", activebackground="#34495E",
            relief=tk.FLAT, padx=6, pady=3,
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side=tk.RIGHT)

        # 狀態列
        self.status_var = tk.StringVar(value="就緒，按「開始監測」後會自動尋找遊戲視窗")
        self._lbl(f, textvariable=self.status_var,
                  font=("Microsoft JhengHei UI", 8),
                  fg="#666688", bg=BG, wraplength=380,
                  justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 0))

    def _build_db(self, f):
        cols = ("question", "answer")
        self.db_tree = ttk.Treeview(f, columns=cols, show="headings", height=18)
        self.db_tree.heading("question", text="題目")
        self.db_tree.heading("answer",   text="答案")
        self.db_tree.column("question",  width=300)
        self.db_tree.column("answer",    width=50, anchor="center")

        vsb = ttk.Scrollbar(f, orient="vertical", command=self.db_tree.yview)
        self.db_tree.configure(yscrollcommand=vsb.set)
        self.db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_entry).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_db).pack(side=tk.LEFT)

        self._refresh_db()

    def _build_cfg(self, f):
        self._cfg_vars = {}

        def row(parent, label, key, desc=""):
            r = tk.Frame(parent, bg=BG2)
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI", 9),
                     width=22, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self.config.get(key, "")))
            self._cfg_vars[key] = var
            tk.Entry(r, textvariable=var, width=8,
                     bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=4)
            if desc:
                tk.Label(r, text=desc, bg=BG2, fg=TEXT_DIM,
                         font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT)

        # API Key
        tk.Label(f, text="Claude API Key（辨識題目用）", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        api_row = tk.Frame(f, bg=BG2)
        api_row.pack(fill=tk.X, pady=2)
        tk.Label(api_row, text="ANTHROPIC_API_KEY", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI", 9),
                 width=22, anchor="w").pack(side=tk.LEFT)
        api_var = tk.StringVar(value=self.config.get("api_key", ""))
        self._cfg_vars["api_key"] = api_var
        api_entry = tk.Entry(api_row, textvariable=api_var, width=28, show="*",
                             bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                             relief=tk.FLAT)
        api_entry.pack(side=tk.LEFT, padx=4)
        def _toggle_show(btn=None, entry=api_entry):
            if entry.cget("show") == "*":
                entry.configure(show="")
                if btn: btn.configure(text="隱藏")
            else:
                entry.configure(show="*")
                if btn: btn.configure(text="顯示")
        show_btn = tk.Button(api_row, text="顯示", bg=BG2, fg=TEXT_DIM,
                             relief=tk.FLAT, padx=4, font=("Microsoft JhengHei UI", 8),
                             command=lambda: _toggle_show(show_btn))
        show_btn.pack(side=tk.LEFT)
        tk.Label(f, text="留空則使用 Windows OCR（效果較差）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(anchor="w", padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="彈窗偵測設定", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        row(f, "偵測點 X 比例",   "popup_check_x",               "0.0–1.0")
        row(f, "偵測點 Y 比例",   "popup_check_y",               "0.0–1.0")
        row(f, "亮度門檻",        "popup_brightness_threshold",  "低於此值=彈窗 (0–255)")
        row(f, "題庫比對相似度",  "match_threshold",             "0.0–1.0（預設 0.72）")

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="題目區域（相對座標）", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        for sub in ["left", "top", "right", "bottom"]:
            r2 = tk.Frame(f, bg=BG2)
            r2.pack(fill=tk.X, pady=1)
            tk.Label(r2, text=f"  question_region.{sub}", bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI", 9), width=22, anchor="w").pack(side=tk.LEFT)
            val = self.config.get("question_region", {}).get(sub, 0)
            var = tk.StringVar(value=str(val))
            self._cfg_vars[f"question_region.{sub}"] = var
            tk.Entry(r2, textvariable=var, width=8,
                     bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack()
        ttk.Button(btn_row, text="儲存設定",     command=self._apply_cfg).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試亮度",     command=self._test_brightness).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試截圖辨識", command=self._test_recognition).pack(side=tk.LEFT)

    # ── 控制 ──

    def _toggle_pin(self):
        self._pinned = not self._pinned
        if self._pinned:
            self.pin_btn.configure(fg="#F1C40F")
            self.root.attributes("-topmost", True)
            self.root.deiconify()
        else:
            self.pin_btn.configure(fg="#555577")
            self.root.attributes("-topmost", False)

    def _toggle_monitor(self):
        if self._thread and self._thread.is_alive():
            self.detector.stop()
            self.start_btn.configure(text="開始監測", bg="#2ECC71")
            self._set_status("已停止")
        else:
            self.detector = SidestandDetector(self.config, self.db)
            self.start_btn.configure(text="停止監測", bg="#C0392B")
            self._thread = threading.Thread(
                target=self.detector.run,
                args=(self._on_result, self._set_status, self._on_error),
                kwargs={"on_popup_gone": self._on_popup_gone},
                daemon=True,
            )
            self._thread.start()

    def _on_result(self, result):
        self._current = result
        if not self._pinned:
            self.root.after(0, self._popup_window)
        self.root.after(0, self._show_result, result)

    def _popup_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        if not self._pinned:
            self.root.after(500, lambda: self.root.attributes("-topmost", False))

    def _on_popup_gone(self):
        if not self._pinned:
            self.root.after(3000, self._auto_hide)

    def _auto_hide(self):
        if not self._pinned:
            self.root.attributes("-topmost", False)
            self.root.lower()

    def _on_error(self, msg):
        self.root.after(0, lambda: [
            messagebox.showerror("錯誤", msg),
            self.start_btn.configure(text="開始監測", bg="#2ECC71"),
        ])

    def _set_status(self, msg):
        self.root.after(0, lambda m=msg: self.status_var.set(m))

    def _show_result(self, result):
        ans      = result.get("answer")
        question = result.get("question", "")
        sim      = result.get("similarity")
        recog    = result.get("recognized", "")

        if ans == "O":
            self.ans_var.set("O")
            self.ans_lbl.configure(fg=COL_O)
        elif ans == "X":
            self.ans_var.set("X")
            self.ans_lbl.configure(fg=COL_X)
        else:
            self.ans_var.set("?")
            self.ans_lbl.configure(fg=COL_UNK)

        self.q_var.set(question[:60] + ("…" if len(question) > 60 else ""))

        if sim is not None:
            self.source_var.set(f"相似度 {sim:.0%}　辨識：{recog[:20]}")
        else:
            self.source_var.set("未找到，可手動存入題庫")

        self.save_btn.configure(state=tk.NORMAL if question else tk.DISABLED)

    def _save_to_db(self):
        if not self._current:
            return
        q   = self._current.get("question", "")
        ans = self._current.get("answer")
        if not q:
            return
        # 若答案未知，彈出選擇
        if not ans:
            win = tk.Toplevel(self.root)
            win.title("選擇答案")
            win.configure(bg=BG)
            win.attributes("-topmost", True)
            win.resizable(False, False)
            tk.Label(win, text=f"題目：{q[:40]}", bg=BG, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI", 10), padx=12, pady=8).pack()
            chosen = tk.StringVar()
            btn_row = tk.Frame(win, bg=BG)
            btn_row.pack(pady=(0, 10))
            def pick(v):
                chosen.set(v)
                win.destroy()
            tk.Button(btn_row, text="O（正確）", font=("Microsoft JhengHei UI", 14, "bold"),
                      bg=COL_O, fg="white", relief=tk.FLAT, padx=14, pady=6,
                      command=lambda: pick("O")).pack(side=tk.LEFT, padx=8)
            tk.Button(btn_row, text="X（錯誤）", font=("Microsoft JhengHei UI", 14, "bold"),
                      bg=COL_X, fg="white", relief=tk.FLAT, padx=14, pady=6,
                      command=lambda: pick("X")).pack(side=tk.LEFT, padx=8)
            win.wait_window()
            if not chosen.get():
                return
            ans = chosen.get()
            self._current["answer"] = ans
            self._show_result(self._current)

        self.db.add(q, ans)
        self._set_status(f"已存入題庫：{q[:25]}…")
        self._refresh_db()

    def _delete_entry(self):
        sel = self.db_tree.selection()
        if not sel:
            return
        idx = self.db_tree.index(sel[0])
        if messagebox.askyesno("刪除", "確定要刪除這筆題庫資料？"):
            self.db.delete(idx)
            self._refresh_db()

    def _refresh_db(self):
        for item in self.db_tree.get_children():
            self.db_tree.delete(item)
        for e in self.db.entries:
            self.db_tree.insert("", "end", values=(
                e.get("question", "")[:50],
                e.get("answer", "?"),
            ))

    def _apply_cfg(self):
        _str_keys = {"api_key"}
        for key, var in self._cfg_vars.items():
            raw = var.get()
            if key in _str_keys:
                self.config[key] = raw
                continue
            try:
                val = float(raw)
                if "." in key:
                    region_key, sub = key.split(".", 1)
                    if region_key not in self.config:
                        self.config[region_key] = {}
                    self.config[region_key][sub] = val
                else:
                    self.config[key] = val
            except ValueError:
                pass
        self.detector.config = self.config
        self._save_config()
        messagebox.showinfo("設定", "設定已儲存")

    def _test_brightness(self):
        found = self.detector.find_window()
        if not found:
            messagebox.showwarning("提示", "找不到遊戲視窗")
            return
        hwnd, _ = found
        try:
            img, w, h = capture_window(hwnd)
            b = self.detector.sample_brightness(img, w, h)
            messagebox.showinfo(
                "亮度測試",
                f"偵測點目前亮度：{b:.1f}\n"
                f"目前門檻：{self.config.get('popup_brightness_threshold', 80)}\n\n"
                f"彈窗出現時，亮度應低於門檻值。",
            )
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _test_recognition(self):
        found = self.detector.find_window()
        if not found:
            messagebox.showwarning("提示", "找不到遊戲視窗，請先開啟遊戲")
            return
        hwnd, title = found

        win = tk.Toplevel(self.root)
        win.title("截圖辨識測試")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)

        tk.Label(win, text="截圖辨識測試", bg=BG, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 12, "bold")).pack(pady=(8, 2))
        status_lbl = tk.Label(win, text="截圖中…", bg=BG, fg=TEXT_DIM,
                              font=("Microsoft JhengHei UI", 9))
        status_lbl.pack()
        preview_lbl = tk.Label(win, bg="#111122", relief=tk.SUNKEN,
                               text="（預覽）", fg=TEXT_DIM,
                               font=("Microsoft JhengHei UI", 8))
        preview_lbl.pack(padx=12, pady=6, ipadx=4, ipady=4)
        result_txt = tk.Text(win, bg=BG2, fg=TEXT_NORM, height=10, width=50,
                             font=("Microsoft JhengHei UI", 10),
                             relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD)
        result_txt.pack(padx=10, pady=(0, 10))

        result_txt.tag_configure("ok",   foreground="#2ECC71")
        result_txt.tag_configure("warn", foreground="#E67E22")
        result_txt.tag_configure("dim",  foreground=TEXT_DIM)
        result_txt.tag_configure("head", foreground="#FFAA00",
                                  font=("Microsoft JhengHei UI", 10, "bold"))

        def _append(text, tag=None):
            result_txt.configure(state=tk.NORMAL)
            if tag:
                result_txt.insert("end", text, tag)
            else:
                result_txt.insert("end", text)
            result_txt.configure(state=tk.DISABLED)

        def run():
            try:
                img, w, h  = capture_window(hwnd)
                brightness  = self.detector.sample_brightness(img, w, h)
                threshold   = self.config.get("popup_brightness_threshold", 80)
                popup_ok    = brightness < threshold

                full_img = self.detector._crop(img, w, h, "popup_full_region")
                pw, ph2  = full_img.size
                scale    = min(380 / pw, 1.0)
                preview  = full_img.resize((int(pw * scale), max(1, int(ph2 * scale))),
                                           Image.Resampling.LANCZOS)
                tk_img   = ImageTk.PhotoImage(preview)

                def update_ui():
                    preview_lbl.configure(image=tk_img, text="")
                    preview_lbl.image = tk_img
                    _append(f"遊戲：{title}\n", "dim")
                    _append(f"亮度：{brightness:.1f}  門檻：{threshold}\n")
                    if popup_ok:
                        _append("→ 彈窗已偵測到\n", "ok")
                    else:
                        _append("→ 彈窗未偵測到（亮度高於門檻）\n", "warn")
                        status_lbl.configure(text="完成（彈窗未出現）")
                        return

                    api_key = self.config.get("api_key", "").strip()
                    q_text  = ""
                    if api_key:
                        _append("\nClaude API 辨識中…\n", "dim")
                        status_lbl.configure(text="API 辨識中…")
                        q_text = claude_read_question(full_img, api_key)
                        src = "Claude API"
                    else:
                        q_text = ocr_image(self.detector._crop(img, w, h, "question_region"))
                        src = "Windows OCR"

                    _append(f"\n辨識方式：{src}\n", "dim")
                    _append("辨識文字：", "head")
                    _append(f"{q_text or '（無法辨識）'}\n")

                    if q_text:
                        threshold_m = self.config.get("match_threshold", 0.72)
                        entry = self.db.lookup(q_text, threshold_m)
                        if entry:
                            _append(f"\n題庫命中！相似度 {entry['similarity']:.0%}\n", "ok")
                            _append(f"答案：{entry['answer']}\n", "head")
                            _append(f"題庫題目：{entry['question']}\n", "dim")
                        else:
                            _append("\n題庫未找到此題\n", "warn")

                    status_lbl.configure(text="辨識完成")

                win.after(0, update_ui)

            except Exception as e:
                win.after(0, lambda: status_lbl.configure(text=f"錯誤：{e}"))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    app  = SidestandApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

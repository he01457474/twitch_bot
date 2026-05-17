#!/usr/bin/env python3
"""大俠四選一輔助 - 黃易群俠傳之風起雙龍 答題顯示工具"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import json
import os
import sys
import ctypes
import re
import io
import subprocess
import urllib.request
import urllib.parse
import win32gui
import win32ui
from PIL import Image, ImageTk

# 隱藏 CMD 視窗
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

DB_FILE  = os.path.join(_APP_DIR, "quiz_database.json")
CFG_FILE = os.path.join(_APP_DIR, "quiz_config.json")

GAME_TITLE_KEYWORDS = ["黃易", "雙龍", "風起", "群俠"]

# 彈窗出現時，此區域像素平均亮度應低於門檻值
# 相對座標（0.0–1.0），對應遊戲視窗 client area
DEFAULT_CONFIG = {
    "popup_check_x": 0.45,           # 亮度偵測點 X 比例
    "popup_check_y": 0.10,           # 亮度偵測點 Y 比例
    "popup_brightness_threshold": 80, # 低於此值視為彈窗出現
    "question_region": {             # 題目文字區域
        "left": 0.17, "top": 0.12,
        "right": 0.74, "bottom": 0.27,
    },
    "options_region": {              # 選項文字區域
        "left": 0.17, "top": 0.27,
        "right": 0.74, "bottom": 0.34,
    },
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
    """捕捉遊戲視窗 client area，回傳 (PIL Image, width, height)。"""
    rect   = win32gui.GetClientRect(hwnd)
    w, h   = rect[2], rect[3]
    hwndDC = win32gui.GetDC(hwnd)
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    bmp    = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(bmp)
    saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), 0x00CC0020)
    info   = bmp.GetInfo()
    raw    = bmp.GetBitmapBits(True)
    win32gui.DeleteObject(bmp.GetHandle())
    saveDC.DeleteDC(); mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    img = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                           raw, "raw", "BGRX", 0, 1)
    return img, w, h


# ── 感知哈希 ──────────────────────────────────────────────────────────────────

def compute_phash(img, size=8):
    """計算圖片的平均感知哈希，回傳 int。"""
    gray    = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels  = list(gray.getdata())
    avg     = sum(pixels) / len(pixels)
    result  = 0
    for p in pixels:
        result = (result << 1) | (1 if p > avg else 0)
    return result

def phash_distance(h1, h2):
    return bin(h1 ^ h2).count('1')


# ── Windows OCR ───────────────────────────────────────────────────────────────

def ocr_image(pil_img):
    """用 Windows OCR 辨識 PIL Image，回傳文字。"""
    try:
        buf = io.BytesIO()
        img = pil_img.convert("RGB")
        if img.width < 400:
            scale = max(2, 400 // img.width)
            img = img.resize((img.width * scale, img.height * scale),
                             Image.Resampling.LANCZOS)
        img.save(buf, format="PNG")
        result = subprocess.run(
            [sys.executable, "-c", _OCR_SCRIPT],
            input=buf.getvalue(),
            capture_output=True,
            timeout=12,
        )
        return result.stdout.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


# ── 網路搜尋 ──────────────────────────────────────────────────────────────────

def web_search_answer(question, options):
    """搜尋題目答案。回傳 (answer_idx 1–4 or None, source_str)。"""
    query = question.strip() + " 答案"
    engines = [
        ("DuckDuckGo", "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)),
        ("Google",     "https://www.google.com/search?q=" + urllib.parse.quote(query)),
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for name, url in engines:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            counts = []
            for opt in options:
                counts.append(text.count(opt.strip()) if opt and opt.strip() else 0)
            max_c = max(counts)
            if max_c > 0:
                best = counts.index(max_c) + 1
                return best, f"{name}（出現 {max_c} 次）"
        except Exception:
            continue
    return None, ""


# ── 題庫 ──────────────────────────────────────────────────────────────────────

class QuizDatabase:
    PHASH_THRESHOLD = 8   # Hamming 距離小於此值視為相同題目

    def __init__(self, path):
        self.path    = path
        self.entries = []
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.entries = json.load(f).get("entries", [])
            except Exception:
                self.entries = []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries}, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)

    def lookup(self, ph, text=""):
        """先用 phash 找，找不到再用文字比對。回傳 entry or None。"""
        if ph:
            for e in self.entries:
                if e.get("phash") and phash_distance(ph, e["phash"]) <= self.PHASH_THRESHOLD:
                    return e
        if text:
            text = text.strip()
            for e in self.entries:
                q = e.get("question", "").strip()
                if not q:
                    continue
                if q == text:
                    return e
                if len(text) >= 4:
                    common = sum(a == b for a, b in zip(q, text))
                    if common / max(len(q), len(text)) >= 0.85:
                        return e
        return None

    def upsert(self, ph, question, answer_idx, answer_text, options):
        entry = {"phash": ph, "question": question,
                 "answer_idx": answer_idx, "answer_text": answer_text,
                 "options": options}
        for i, e in enumerate(self.entries):
            if e.get("question", "").strip() == question.strip():
                self.entries[i] = entry
                self.save()
                return
        self.entries.append(entry)
        self.save()

    def delete(self, idx):
        if 0 <= idx < len(self.entries):
            self.entries.pop(idx)
            self.save()


# ── 偵測邏輯 ──────────────────────────────────────────────────────────────────

class QuizDetector:
    def __init__(self, config, db):
        self.config    = config
        self.db        = db
        self._stop     = threading.Event()
        self.hwnd      = None
        self._last_ph  = None
        self._last_q   = ""
        self._popup_on = False

    def find_window(self):
        found = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            for kw in GAME_TITLE_KEYWORDS:
                if kw in title:
                    found.append((hwnd, title))
                    break
        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    def _crop(self, img, w, h, region_key):
        r  = self.config.get(region_key, {})
        x1 = int(r.get("left",   0.0) * w)
        y1 = int(r.get("top",    0.0) * h)
        x2 = int(r.get("right",  1.0) * w)
        y2 = int(r.get("bottom", 1.0) * h)
        return img.crop((max(0, x1), max(0, y1), min(w, x2), min(h, y2)))

    def _popup_visible(self, img, w, h):
        cx = int(self.config.get("popup_check_x", 0.45) * w)
        cy = int(self.config.get("popup_check_y", 0.10) * h)
        r  = 6
        region = img.crop((max(0, cx - r), max(0, cy - r),
                           min(w, cx + r), min(h, cy + r)))
        pixels = list(region.getdata())
        if not pixels:
            return False
        brightness = sum(sum(p) for p in pixels) / (len(pixels) * 3)
        threshold  = self.config.get("popup_brightness_threshold", 80)
        return brightness < threshold

    def sample_brightness(self, img, w, h):
        """回傳偵測點亮度值（供 UI 顯示調整用）。"""
        cx = int(self.config.get("popup_check_x", 0.45) * w)
        cy = int(self.config.get("popup_check_y", 0.10) * h)
        r  = 6
        region = img.crop((max(0, cx - r), max(0, cy - r),
                           min(w, cx + r), min(h, cy + r)))
        pixels = list(region.getdata())
        if not pixels:
            return 255
        return sum(sum(p) for p in pixels) / (len(pixels) * 3)

    def _parse_options(self, text):
        """將 OCR 文字拆成 4 個選項。"""
        if not text:
            return ["", "", "", ""]
        # 嘗試用 A/B/C/D 或 1/2/3/4 分割
        for pattern in [r'[ABCD][\.、\s]', r'[1234][\.、\s]']:
            parts = re.split(pattern, text)
            if len(parts) >= 5:   # 有前綴 + 4段
                opts = [p.strip() for p in parts[1:5]]
                return opts
        # 用換行分割
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) >= 4:
            return lines[:4]
        # 用空格大略分割（4 等份）
        words = text.split()
        if len(words) >= 4:
            n = len(words)
            q = n // 4
            return [" ".join(words[i*q:(i+1)*q]) for i in range(4)]
        return (lines + ["", "", "", ""])[:4]

    def process_frame(self, img, w, h, on_status):
        """處理一幀截圖。回傳 result dict 或 None。"""
        visible = self._popup_visible(img, w, h)

        if not visible:
            if self._popup_on:
                self._popup_on = False
                self._last_ph  = None
                self._last_q   = ""
                on_status("等待題目…")
            return None

        if not self._popup_on:
            self._popup_on = True

        q_img = self._crop(img, w, h, "question_region")
        ph    = compute_phash(q_img)

        # 同一題跳過
        if self._last_ph is not None and phash_distance(ph, self._last_ph) < 4:
            return None

        self._last_ph = ph
        on_status("偵測到題目，查詢題庫…")

        # 1. 題庫 phash 查詢
        entry = self.db.lookup(ph)
        if entry:
            self._last_q = entry["question"]
            on_status(f"題庫命中：{entry['question'][:20]}")
            return dict(entry, source="題庫", phash=ph)

        # 2. OCR 辨識
        on_status("題庫未命中，OCR 辨識中…")
        q_text   = ocr_image(q_img)
        opt_img  = self._crop(img, w, h, "options_region")
        opt_text = ocr_image(opt_img)
        options  = self._parse_options(opt_text)

        if not q_text:
            on_status("OCR 辨識失敗，請確認視窗是否在前景")
            return None

        self._last_q = q_text

        # 3. 題庫文字比對
        entry = self.db.lookup(None, q_text)
        if entry:
            on_status(f"題庫命中（文字）：{q_text[:20]}")
            return dict(entry, options=options or entry.get("options", []),
                        source="題庫（文字比對）", phash=ph)

        # 4. 網路搜尋
        on_status("題庫未找到，上網搜尋中…")
        ans_idx, source = web_search_answer(q_text, options)
        ans_text = options[ans_idx - 1] if ans_idx and ans_idx <= len(options) else ""
        on_status(source or "網路搜尋無結果")
        return {
            "question":    q_text,
            "answer_idx":  ans_idx,
            "answer_text": ans_text,
            "options":     options,
            "source":      source or "網路搜尋（無結果）",
            "phash":       ph,
        }

    def run(self, on_result, on_status, on_error):
        """主監測迴圈（在子執行緒執行）。"""
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
                img, w, h = capture_window(self.hwnd)
                result    = self.process_frame(img, w, h, on_status)
                if result:
                    on_result(result)
            except Exception as e:
                on_status(f"錯誤：{e}")
            self._stop.wait(0.5)

    def stop(self):
        self._stop.set()


# ── GUI ───────────────────────────────────────────────────────────────────────

BG         = "#0F0F1A"
BG2        = "#1A1A2E"
ACCENT     = "#E94560"
TEXT_DIM   = "#888888"
TEXT_NORM  = "#CCCCCC"
OPT_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"]

class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("大俠四選一輔助")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)

        self.config   = self._load_config()
        self.db       = QuizDatabase(DB_FILE)
        self.detector = QuizDetector(self.config, self.db)
        self._thread  = None
        self._current = None

        self._build_ui()

    # ── 設定 ──

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

    # ── UI 建構 ──

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG2, foreground=TEXT_NORM, bordercolor=BG)
        style.configure("TNotebook",      background=BG)
        style.configure("TNotebook.Tab",  background=BG2, foreground=TEXT_NORM, padding=[8, 4])
        style.map("TNotebook.Tab",        background=[("selected", BG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        f_main = tk.Frame(nb, bg=BG, padx=8, pady=6)
        f_db   = tk.Frame(nb, bg=BG2)
        f_cfg  = tk.Frame(nb, bg=BG2, padx=10, pady=8)

        nb.add(f_main, text=" 答題 ")
        nb.add(f_db,   text=" 題庫 ")
        nb.add(f_cfg,  text=" 設定 ")

        self._build_main(f_main)
        self._build_db(f_db)
        self._build_cfg(f_cfg)

    def _lbl(self, parent, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        return tk.Label(parent, **kw)

    def _build_main(self, f):
        # 答案號碼（超大）
        self.ans_num_var = tk.StringVar(value="─")
        self._lbl(f, textvariable=self.ans_num_var,
                  font=("Microsoft JhengHei UI", 96, "bold"),
                  fg=ACCENT, bg=BG, pady=0).pack(fill=tk.X)

        # 答案文字
        self.ans_text_var = tk.StringVar(value="")
        self._lbl(f, textvariable=self.ans_text_var,
                  font=("Microsoft JhengHei UI", 14, "bold"),
                  fg="#FFAA00", bg=BG, pady=2).pack(fill=tk.X)

        # 題目文字
        self.q_var = tk.StringVar(value="等待題目出現…")
        self._lbl(f, textvariable=self.q_var,
                  font=("Microsoft JhengHei UI", 10),
                  fg=TEXT_DIM, bg=BG, wraplength=390,
                  justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 2))

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=4)

        # 選項列表
        self.opt_vars = []
        for i in range(4):
            v = tk.StringVar(value=f"  {i+1}. ")
            self.opt_vars.append(v)
            self._lbl(f, textvariable=v,
                      font=("Microsoft JhengHei UI", 11),
                      fg=OPT_COLORS[i], bg=BG,
                      anchor="w", justify=tk.LEFT).pack(fill=tk.X)

        # 來源
        self.source_var = tk.StringVar(value="")
        self._lbl(f, textvariable=self.source_var,
                  font=("Microsoft JhengHei UI", 8),
                  fg="#555577", bg=BG).pack(pady=(4, 0))

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

        # 修正答案
        self.fix_btn = tk.Button(
            btn_row, text="修正答案",
            font=("Microsoft JhengHei UI", 11),
            bg="#8E44AD", fg="white", activebackground="#7D3C98",
            relief=tk.FLAT, padx=10, pady=4,
            command=self._fix_answer, state=tk.DISABLED,
        )
        self.fix_btn.pack(side=tk.LEFT, padx=(6, 0))

        # 狀態列
        self.status_var = tk.StringVar(value="就緒，按「開始監測」後會自動尋找遊戲視窗")
        self._lbl(f, textvariable=self.status_var,
                  font=("Microsoft JhengHei UI", 8),
                  fg="#666688", bg=BG, wraplength=390,
                  justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 0))

    def _build_db(self, f):
        cols = ("question", "answer", "source")
        self.db_tree = ttk.Treeview(f, columns=cols, show="headings", height=16)
        self.db_tree.heading("question", text="題目")
        self.db_tree.heading("answer",   text="答案")
        self.db_tree.heading("source",   text="來源")
        self.db_tree.column("question",  width=220)
        self.db_tree.column("answer",    width=120)
        self.db_tree.column("source",    width=80)

        vsb = ttk.Scrollbar(f, orient="vertical",   command=self.db_tree.yview)
        self.db_tree.configure(yscrollcommand=vsb.set)

        self.db_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_entry).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_db).pack(side=tk.LEFT)

        self._refresh_db()

    def _build_cfg(self, f):
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

        self._cfg_vars = {}

        tk.Label(f, text="彈窗偵測設定", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        row(f, "偵測點 X 比例", "popup_check_x", "0.0–1.0，視窗左→右")
        row(f, "偵測點 Y 比例", "popup_check_y", "0.0–1.0，視窗上→下")
        row(f, "亮度門檻", "popup_brightness_threshold", "低於此值=彈窗出現 (0–255)")

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
        tk.Label(f, text="選項區域（相對座標）", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 10, "bold")).pack(anchor="w")
        for sub in ["left", "top", "right", "bottom"]:
            r3 = tk.Frame(f, bg=BG2)
            r3.pack(fill=tk.X, pady=1)
            tk.Label(r3, text=f"  options_region.{sub}", bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI", 9), width=22, anchor="w").pack(side=tk.LEFT)
            val = self.config.get("options_region", {}).get(sub, 0)
            var = tk.StringVar(value=str(val))
            self._cfg_vars[f"options_region.{sub}"] = var
            tk.Entry(r3, textvariable=var, width=8,
                     bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack()
        ttk.Button(btn_row, text="儲存設定", command=self._apply_cfg).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試偵測點亮度", command=self._test_brightness).pack(side=tk.LEFT)

    # ── 控制 ──

    def _toggle_monitor(self):
        if self._thread and self._thread.is_alive():
            self.detector.stop()
            self.start_btn.configure(text="開始監測", bg="#2ECC71")
            self._set_status("已停止")
        else:
            self.detector = QuizDetector(self.config, self.db)
            self.start_btn.configure(text="停止監測", bg="#C0392B")
            self._thread = threading.Thread(
                target=self.detector.run,
                args=(self._on_result, self._set_status, self._on_error),
                daemon=True,
            )
            self._thread.start()

    def _on_result(self, result):
        self._current = result
        self.root.after(0, self._show_result, result)

    def _on_error(self, msg):
        self.root.after(0, lambda: [
            messagebox.showerror("錯誤", msg),
            self.start_btn.configure(text="開始監測", bg="#2ECC71"),
        ])

    def _set_status(self, msg):
        self.root.after(0, lambda m=msg: self.status_var.set(m))

    def _show_result(self, result):
        idx      = result.get("answer_idx")
        ans_text = result.get("answer_text", "")
        question = result.get("question", "")
        options  = result.get("options", [])
        source   = result.get("source", "")

        if idx:
            self.ans_num_var.set(str(idx))
        else:
            self.ans_num_var.set("?")
        self.ans_text_var.set(ans_text)
        self.q_var.set(question[:50] + ("…" if len(question) > 50 else ""))
        self.source_var.set(f"來源：{source}" if source else "")

        for i, (var, color) in enumerate(zip(self.opt_vars, OPT_COLORS)):
            opt  = options[i] if i < len(options) else ""
            star = "★ " if idx == i + 1 else "   "
            var.set(f"{star}{i+1}. {opt}")

        has_q = bool(question)
        self.save_btn.configure(state=tk.NORMAL if has_q else tk.DISABLED)
        self.fix_btn.configure(state=tk.NORMAL if has_q else tk.DISABLED)

    def _save_to_db(self):
        if not self._current:
            return
        r   = self._current
        q   = r.get("question", "")
        idx = r.get("answer_idx")
        if not q or not idx:
            messagebox.showwarning("提示", "請先確認題目和答案")
            return
        self.db.upsert(r.get("phash") or 0, q, idx,
                       r.get("answer_text", ""), r.get("options", []))
        self._set_status(f"已存入題庫：{q[:25]}…")
        self._refresh_db()

    def _fix_answer(self):
        if not self._current:
            return
        choices = ["1", "2", "3", "4"]
        dlg = simpledialog.askstring(
            "修正答案", "請輸入正確答案編號（1–4）：",
            initialvalue=str(self._current.get("answer_idx") or ""),
            parent=self.root,
        )
        if dlg and dlg.strip() in choices:
            idx      = int(dlg.strip())
            opts     = self._current.get("options", [])
            ans_text = opts[idx - 1] if idx <= len(opts) else ""
            self._current["answer_idx"]  = idx
            self._current["answer_text"] = ans_text
            self._show_result(self._current)

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
            q   = e.get("question", "")[:28]
            idx = e.get("answer_idx", "?")
            t   = e.get("answer_text", "")[:15]
            src = e.get("source", "")[:8]
            self.db_tree.insert("", "end", values=(q, f"{idx}. {t}", src))

    def _apply_cfg(self):
        for key, var in self._cfg_vars.items():
            try:
                val = float(var.get())
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
                f"彈窗出現時，亮度應低於門檻值。\n"
                f"請在彈窗消失時測一次、出現時再測一次，\n"
                f"取兩次的中間值作為門檻。"
            )
        except Exception as e:
            messagebox.showerror("錯誤", str(e))


def main():
    root = tk.Tk()
    app  = QuizApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

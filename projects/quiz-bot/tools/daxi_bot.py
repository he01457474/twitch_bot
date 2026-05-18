#!/usr/bin/env python3
"""黃易群俠傳 大俠活動輔助 — 四選一 + 選邊站 合一介面"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import json
import os
import sys
import ctypes
import re
import io
import subprocess
import datetime
import time
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

QUIZ4_DB_FILE     = os.path.join(_APP_DIR, "quiz_database.json")
SIDESTAND_DB_FILE = os.path.join(_APP_DIR, "sidestand_database.json")
CFG_FILE          = os.path.join(_APP_DIR, "daxi_config.json")

GAME_TITLE_KEYWORDS = ["黃易", "雙龍", "風起", "群俠"]

DEFAULT_CONFIG = {
    "popup_check_x": 0.45,
    "popup_check_y": 0.10,
    "popup_brightness_threshold": 80,
    "question_region":  {"left": 0.17, "top": 0.12, "right": 0.74, "bottom": 0.27},
    "options_region":   {"left": 0.17, "top": 0.27, "right": 0.74, "bottom": 0.34},
    "popup_full_region":{"left": 0.15, "top": 0.09, "right": 0.76, "bottom": 0.36},
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

# ── 截圖 / Hash / OCR ──────────────────────────────────────────────────────────

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
    saveDC.DeleteDC(); mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    win32gui.DeleteObject(bmp.GetHandle())
    return img, w, h

def compute_phash(img):
    small  = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    avg    = sum(pixels) / 64
    bits   = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits

def phash_distance(a, b):
    x = a ^ b
    c = 0
    while x:
        c += x & 1; x >>= 1
    return c

def ocr_image(pil_img, on_detail=None):
    try:
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        proc = subprocess.run(
            [sys.executable, "-c", _OCR_SCRIPT],
            input=buf.getvalue(), capture_output=True, timeout=10,
        )
        if proc.returncode != 0 and on_detail:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            on_detail(f"OCR 程序錯誤（returncode={proc.returncode}）：{err[:120]}")
        elif not proc.stdout.strip() and proc.stderr.strip() and on_detail:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            on_detail(f"OCR 無結果，stderr：{err[:120]}")
        return proc.stdout.decode("utf-8", errors="replace").strip()
    except Exception as e:
        if on_detail: on_detail(f"OCR 例外：{type(e).__name__}: {e}")
        return ""

def claude_read_popup(pil_img, api_key, on_detail=None):
    """回傳 (question_str, options_list) — 四選一用。"""
    try:
        import anthropic, base64, json as _j
        buf = io.BytesIO()
        img = pil_img.convert("RGB")
        if max(img.width, img.height) < 600:
            s = max(2, 600 // max(img.width, img.height))
            img = img.resize((img.width * s, img.height * s), Image.Resampling.LANCZOS)
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": '這是一個武俠遊戲的問答截圖（繁體中文）。請讀出題目和選項，以JSON格式回傳（只輸出JSON）：{"question":"完整題目文字","options":["選項1","選項2","選項3","選項4"]}'},
            ]}],
        )
        raw  = re.sub(r'^```[a-z]*\n?', '', resp.content[0].text.strip()).rstrip('`').strip()
        data = _j.loads(raw)
        q    = data.get("question", "").strip()
        opts = [str(o).strip() for o in data.get("options", [])[:4]]
        while len(opts) < 4: opts.append("")
        return q, opts
    except Exception as e:
        if on_detail: on_detail(f"API(popup) 錯誤：{type(e).__name__}: {str(e)[:100]}")
        return "", []

def claude_read_question(pil_img, api_key, on_detail=None):
    """回傳 question_str — 選邊站用（只讀題目）。"""
    try:
        import anthropic, base64
        buf = io.BytesIO()
        img = pil_img.convert("RGB")
        if max(img.width, img.height) < 600:
            s = max(2, 600 // max(img.width, img.height))
            img = img.resize((img.width * s, img.height * s), Image.Resampling.LANCZOS)
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=200,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": "這是一個武俠遊戲的問答截圖（繁體中文）。請只輸出題目文字，不要任何選項或說明。"},
            ]}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        if on_detail: on_detail(f"API(question) 錯誤：{type(e).__name__}: {str(e)[:100]}")
        return ""

# ── 題庫 ───────────────────────────────────────────────────────────────────────

class Quiz4Database:
    def __init__(self, path):
        self.path    = path
        self.entries = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 相容 {"entries": [...]} 和 [...] 兩種格式
                if isinstance(data, list):
                    self.entries = data
                else:
                    self.entries = data.get("entries", [])
            except Exception:
                self.entries = []

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries}, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)

    def lookup(self, phash=None, question=None):
        if phash:
            for e in self.entries:
                if e.get("phash") and phash_distance(phash, e["phash"]) < 5:
                    return e
        if question:
            for e in self.entries:
                if SequenceMatcher(None, question, e.get("question","")).ratio() > 0.85:
                    return e
        return None

    def upsert(self, phash, question, answer_idx, answer_text, options):
        for e in self.entries:
            if e.get("question") == question:
                e.update(phash=phash, answer_idx=answer_idx,
                         answer_text=answer_text, options=options)
                self._save(); return
        self.entries.append(dict(phash=phash, question=question,
                                 answer_idx=answer_idx, answer_text=answer_text,
                                 options=options, source="手動"))
        self._save()

    def delete(self, idx):
        if 0 <= idx < len(self.entries):
            self.entries.pop(idx); self._save()


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

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.path)

    def lookup(self, question, threshold=0.72):
        best, best_score = None, 0.0
        for e in self.entries:
            s = SequenceMatcher(None, question, e["question"]).ratio()
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return dict(best, similarity=round(best_score, 3))
        return None

    def add(self, question, answer):
        self.entries.append({"question": question, "answer": answer})
        self._save()

    def delete(self, idx):
        if 0 <= idx < len(self.entries):
            self.entries.pop(idx); self._save()

# ── 偵測器 ─────────────────────────────────────────────────────────────────────

class GameDetector:
    def __init__(self, config, db4, dbs, on_detail=None):
        self.config         = config
        self.db4            = db4
        self.dbs            = dbs
        self.mode           = "quiz4"      # "quiz4" | "sidestand"
        self._stop          = threading.Event()
        self._popup_on      = False
        self._last_ph       = None
        self._last_api_ph   = None
        self._last_api_time = 0.0
        self.hwnd           = None
        self._on_detail     = on_detail or (lambda m: None)

    def set_mode(self, mode):
        self.mode           = mode
        self._popup_on      = False
        self._last_ph       = None
        self._last_api_ph   = None
        self._last_api_time = 0.0

    def find_window(self):
        result = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return
            t = win32gui.GetWindowText(hwnd)
            if any(k in t for k in GAME_TITLE_KEYWORDS):
                result.append((hwnd, t))
        win32gui.EnumWindows(cb, None)
        return result[0] if result else None

    def _crop(self, img, w, h, key):
        r  = self.config.get(key, {})
        x1 = int(r.get("left",  0) * w); y1 = int(r.get("top",    0) * h)
        x2 = int(r.get("right", 1) * w); y2 = int(r.get("bottom", 1) * h)
        return img.crop((x1, y1, x2, y2))

    def sample_brightness(self, img, w, h):
        cx = int(self.config.get("popup_check_x", 0.45) * w)
        cy = int(self.config.get("popup_check_y", 0.10) * h)
        r  = 6
        region = img.crop((max(0,cx-r), max(0,cy-r), min(w,cx+r), min(h,cy+r)))
        pixels = list(region.getdata())
        if not pixels: return 255
        return sum(sum(p) for p in pixels) / (len(pixels) * 3)

    def _can_call_api(self, ph):
        """同一題目只呼叫一次 API：phash 相近 or 冷卻期內直接跳過。"""
        cooldown = self.config.get("api_cooldown", 10)
        if self._last_api_ph is not None and phash_distance(ph, self._last_api_ph) < 10:
            return False
        if time.time() - self._last_api_time < cooldown:
            return False
        return True

    def _record_api_call(self, ph):
        self._last_api_ph   = ph
        self._last_api_time = time.time()

    def _parse_options(self, text):
        if not text: return ["","","",""]
        for pat in [r'[ABCD][\.、\s]', r'[1234][\.、\s]']:
            parts = re.split(pat, text)
            if len(parts) >= 5:
                return [p.strip() for p in parts[1:5]]
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        if len(lines) >= 4: return lines[:4]
        words = text.split()
        if len(words) >= 4:
            q = len(words) // 4
            return [" ".join(words[i*q:(i+1)*q]) for i in range(4)]
        return (lines + ["","","",""])[:4]

    def process_frame(self, img, w, h, on_status):
        visible = self.sample_brightness(img, w, h) < self.config.get("popup_brightness_threshold", 80)
        if not visible:
            if self._popup_on:
                self._popup_on      = False
                self._last_ph       = None
                self._last_api_ph   = None
                self._last_api_time = 0.0
                on_status("等待題目…")
            return None
        if not self._popup_on:
            self._popup_on = True

        q_img = self._crop(img, w, h, "question_region")
        ph    = compute_phash(q_img)
        if ph == 0 or ph == (1 << 64) - 1: return None
        if self._last_ph is not None and phash_distance(ph, self._last_ph) < 4: return None
        self._last_ph = ph
        on_status("偵測到題目…")

        if self.mode == "quiz4":
            return self._process_quiz4(img, w, h, q_img, ph, on_status)
        else:
            return self._process_sidestand(img, w, h, q_img, ph, on_status)

    def _process_quiz4(self, img, w, h, q_img, ph, on_status):
        entry = self.db4.lookup(ph)
        if entry:
            on_status(f"題庫命中")
            return dict(entry, source="題庫", phash=ph)

        api_key = self.config.get("api_key", "").strip()
        q_text, options = "", []
        if api_key and self._can_call_api(ph):
            on_status("Claude API 辨識中…")
            q_text, options = claude_read_popup(
                self._crop(img, w, h, "popup_full_region"), api_key,
                on_detail=self._on_detail)
            self._record_api_call(ph)
        if not q_text:
            on_status("OCR 辨識中…")
            q_text  = ocr_image(q_img, on_detail=self._on_detail)
            opt_img = self._crop(img, w, h, "options_region")
            options = self._parse_options(ocr_image(opt_img))
        if not q_text:
            on_status("辨識失敗"); return None

        entry = self.db4.lookup(question=q_text)
        if entry:
            on_status("題庫命中（文字）")
            return dict(entry, options=options or entry.get("options",[]), source="題庫", phash=ph)

        on_status("題庫未找到")
        return {"question": q_text, "answer_idx": None, "answer_text": "",
                "options": options, "source": "未知", "phash": ph}

    def _process_sidestand(self, img, w, h, q_img, ph, on_status):
        api_key = self.config.get("api_key", "").strip()
        q_text  = ""
        if api_key and self._can_call_api(ph):
            on_status("Claude API 辨識中…")
            q_text = claude_read_question(
                self._crop(img, w, h, "popup_full_region"), api_key,
                on_detail=self._on_detail)
            self._record_api_call(ph)
        if not q_text:
            on_status("OCR 辨識中…")
            q_text = ocr_image(q_img, on_detail=self._on_detail)
        if not q_text:
            on_status("辨識失敗"); return None

        threshold = self.config.get("match_threshold", 0.72)
        entry = self.dbs.lookup(q_text, threshold)
        if entry:
            on_status(f"命中（{entry['similarity']:.0%}）")
            return dict(entry, phash=ph, recognized=q_text)

        on_status("題庫未找到此題")
        return {"question": q_text, "answer": None, "phash": ph, "recognized": q_text}

    def run(self, on_result, on_status, on_error, on_popup_gone=None):
        self._stop.clear()
        found = self.find_window()
        if not found:
            on_error("找不到遊戲視窗，請確認遊戲已開啟"); return
        self.hwnd, title = found
        on_status(f"已連接：{title}")
        while not self._stop.is_set():
            try:
                if not (win32gui.IsWindow(self.hwnd) and win32gui.IsWindowVisible(self.hwnd)):
                    on_error("遊戲視窗已關閉"); return
                img, w, h  = capture_window(self.hwnd)
                was_on     = self._popup_on
                result     = self.process_frame(img, w, h, on_status)
                if result: on_result(result)
                if was_on and not self._popup_on and on_popup_gone:
                    on_popup_gone()
            except Exception as e:
                on_status(f"錯誤：{e}")
            self._stop.wait(0.5)

    def stop(self):
        self._stop.set()

# ── GUI ────────────────────────────────────────────────────────────────────────

BG        = "#0F0F1A"
BG2       = "#1A1A2E"
ACCENT    = "#E94560"
TEXT_DIM  = "#888888"
TEXT_NORM = "#CCCCCC"
OPT_COLORS = ["#FF6B6B","#4ECDC4","#45B7D1","#96CEB4"]
COL_O     = "#2ECC71"
COL_X     = "#E74C3C"
COL_UNK   = "#555577"


class DaxiApp:
    def __init__(self, root):
        self.root    = root
        self.root.title("大俠活動輔助")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", False)
        self.root.resizable(False, False)

        self.config   = self._load_config()
        self.db4      = Quiz4Database(QUIZ4_DB_FILE)
        self.dbs      = SidestandDatabase(SIDESTAND_DB_FILE)
        self.detector = GameDetector(self.config, self.db4, self.dbs)
        self._thread  = None
        self._current = None
        self._pinned  = False
        self._mode    = tk.StringVar(value="quiz4")

        self._build_ui()
        self.root.after(50, lambda: (self.root.lift(), self.root.focus_force()))

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

    def _lbl(self, parent, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        return tk.Label(parent, **kw)

    # ── 建構 UI ──

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG2, foreground=TEXT_NORM, bordercolor=BG)
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_NORM, padding=[8,4])
        style.map("TNotebook.Tab",       background=[("selected", BG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        f_main = tk.Frame(nb, bg=BG,  padx=8, pady=6)
        f_db4  = tk.Frame(nb, bg=BG2)
        f_dbs  = tk.Frame(nb, bg=BG2)
        f_cfg  = tk.Frame(nb, bg=BG2, padx=10, pady=8)

        nb.add(f_main, text=" 答題 ")
        nb.add(f_db4,  text=" 四選一題庫 ")
        nb.add(f_dbs,  text=" 選邊站題庫 ")
        nb.add(f_cfg,  text=" 設定 ")

        self._build_main(f_main)
        self._build_db4(f_db4)
        self._build_dbs(f_dbs)
        self._build_cfg(f_cfg)

    def _build_main(self, f):
        # ── 模式切換 ──
        mode_row = tk.Frame(f, bg=BG)
        mode_row.pack(fill=tk.X, pady=(0, 4))

        self._btn_quiz4 = tk.Button(
            mode_row, text="四選一",
            font=("Microsoft JhengHei UI", 10, "bold"),
            bg=ACCENT, fg="white", activebackground="#C0392B",
            relief=tk.FLAT, padx=14, pady=3,
            command=lambda: self._switch_mode("quiz4"),
        )
        self._btn_quiz4.pack(side=tk.LEFT, padx=(0, 4))

        self._btn_side = tk.Button(
            mode_row, text="選邊站",
            font=("Microsoft JhengHei UI", 10, "bold"),
            bg=BG2, fg=TEXT_DIM, activebackground="#2C3E50",
            relief=tk.FLAT, padx=14, pady=3,
            command=lambda: self._switch_mode("sidestand"),
        )
        self._btn_side.pack(side=tk.LEFT)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=(4, 6))

        # ── 四選一顯示區 ──
        self._frame_quiz4 = tk.Frame(f, bg=BG)

        self.ans_num_var = tk.StringVar(value="─")
        self._lbl(self._frame_quiz4, textvariable=self.ans_num_var,
                  font=("Microsoft JhengHei UI", 96, "bold"),
                  fg=ACCENT, bg=BG, pady=0).pack(fill=tk.X)

        self.ans_text_var = tk.StringVar(value="")
        self._lbl(self._frame_quiz4, textvariable=self.ans_text_var,
                  font=("Microsoft JhengHei UI", 13, "bold"),
                  fg="#FFAA00", bg=BG, pady=2).pack(fill=tk.X)

        # 方位圖
        self._map_canvas = tk.Canvas(self._frame_quiz4, bg=BG, width=160, height=72, highlightthickness=0)
        self._map_canvas.pack(pady=(0, 2))
        CW, CH, GAP = 72, 30, 4
        _zones = [(0,0,1,"1\n左上"),(1,0,2,"2\n右上"),(0,1,4,"4\n左下"),(1,1,3,"3\n右下")]
        self._map_rects = {}; self._map_texts = {}
        x0, y0 = 8, 4
        for col, row, zn, lbl in _zones:
            x1 = x0 + col*(CW+GAP); y1 = y0 + row*(CH+GAP)
            x2, y2 = x1+CW, y1+CH
            rid = self._map_canvas.create_rectangle(x1,y1,x2,y2, fill="#222240", outline="#444466", width=1)
            tid = self._map_canvas.create_text((x1+x2)//2,(y1+y2)//2, text=lbl,
                                               fill="#666688", font=("Microsoft JhengHei UI",8), justify="center")
            self._map_rects[zn]=rid; self._map_texts[zn]=tid

        self.q_var4 = tk.StringVar(value="等待題目出現…")
        self._lbl(self._frame_quiz4, textvariable=self.q_var4,
                  font=("Microsoft JhengHei UI", 10), fg=TEXT_DIM, bg=BG,
                  wraplength=390, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4,2))

        ttk.Separator(self._frame_quiz4, orient="horizontal").pack(fill=tk.X, pady=4)

        self.opt_vars = []
        for i in range(4):
            v = tk.StringVar(value=f"  {i+1}. ")
            self.opt_vars.append(v)
            self._lbl(self._frame_quiz4, textvariable=v,
                      font=("Microsoft JhengHei UI", 11),
                      fg=OPT_COLORS[i], bg=BG, anchor="w").pack(fill=tk.X)

        self.source_var4 = tk.StringVar(value="")
        self._lbl(self._frame_quiz4, textvariable=self.source_var4,
                  font=("Microsoft JhengHei UI", 8), fg="#555577", bg=BG).pack(pady=(4,0))

        # ── 選邊站顯示區 ──
        self._frame_side = tk.Frame(f, bg=BG)

        self.ans_ox_var = tk.StringVar(value="─")
        self.ans_ox_lbl = self._lbl(self._frame_side, textvariable=self.ans_ox_var,
                                    font=("Microsoft JhengHei UI", 120, "bold"),
                                    fg=COL_UNK, bg=BG, pady=0)
        self.ans_ox_lbl.pack(fill=tk.X)

        self.q_vars = tk.StringVar(value="等待題目出現…")
        self._lbl(self._frame_side, textvariable=self.q_vars,
                  font=("Microsoft JhengHei UI", 11), fg=TEXT_NORM, bg=BG,
                  wraplength=380, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4,2))

        self.source_vars = tk.StringVar(value="")
        self._lbl(self._frame_side, textvariable=self.source_vars,
                  font=("Microsoft JhengHei UI", 8), fg=TEXT_DIM, bg=BG).pack(pady=(0,2))

        # 初始顯示四選一
        self._frame_quiz4.pack(fill=tk.X)

        # ── 通知欄 ──
        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=(6, 2))
        notif_frame = tk.Frame(f, bg=BG)
        notif_frame.pack(fill=tk.X, pady=(0, 2))
        tk.Label(notif_frame, text="通知", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 7)).pack(anchor="w")
        self.notif_log = tk.Text(
            notif_frame, bg="#0A0A14", fg=TEXT_DIM,
            height=4, width=1,
            font=("Microsoft JhengHei UI", 8),
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
            cursor="arrow",
        )
        notif_sb = ttk.Scrollbar(notif_frame, orient="vertical",
                                  command=self.notif_log.yview)
        self.notif_log.configure(yscrollcommand=notif_sb.set)
        self.notif_log.pack(side=tk.LEFT, fill=tk.X, expand=True)
        notif_sb.pack(side=tk.RIGHT, fill=tk.Y)
        # 顏色標籤
        self.notif_log.tag_configure("warn",  foreground="#E67E22")
        self.notif_log.tag_configure("ok",    foreground="#2ECC71")
        self.notif_log.tag_configure("info",  foreground="#3498DB")
        self.notif_log.tag_configure("dim",   foreground="#555577")
        self.notif_log.tag_configure("time",  foreground="#444466")

        # ── 共用按鈕列 ──
        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        btn_row = tk.Frame(f, bg=BG)
        btn_row.pack(fill=tk.X)

        self.start_btn = tk.Button(
            btn_row, text="開始監測",
            font=("Microsoft JhengHei UI", 11),
            bg="#2ECC71", fg="white", activebackground="#27AE60",
            relief=tk.FLAT, padx=14, pady=4,
            command=self._toggle_monitor,
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0,6))

        self.save_btn = tk.Button(
            btn_row, text="存入題庫",
            font=("Microsoft JhengHei UI", 11),
            bg="#3498DB", fg="white", activebackground="#2980B9",
            relief=tk.FLAT, padx=14, pady=4,
            command=self._save_to_db, state=tk.DISABLED,
        )
        self.save_btn.pack(side=tk.LEFT)

        self.fix_btn = tk.Button(
            btn_row, text="修正答案",
            font=("Microsoft JhengHei UI", 11),
            bg="#8E44AD", fg="white", activebackground="#7D3C98",
            relief=tk.FLAT, padx=10, pady=4,
            command=self._fix_answer, state=tk.DISABLED,
        )
        self.fix_btn.pack(side=tk.LEFT, padx=(6,0))

        self.pin_btn = tk.Button(
            btn_row, text="📌",
            font=("Segoe UI Emoji", 13),
            bg="#2C3E50", fg="#555577", activebackground="#34495E",
            relief=tk.FLAT, padx=6, pady=3,
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value="就緒，按「開始監測」後會自動尋找遊戲視窗")
        self.status_lbl = self._lbl(f, textvariable=self.status_var,
                  font=("Microsoft JhengHei UI", 8), fg="#666688", bg=BG,
                  wraplength=390, justify=tk.LEFT, anchor="w")
        self.status_lbl.pack(fill=tk.X, pady=(4,0))

    def _switch_mode(self, mode):
        self._mode.set(mode)
        self.detector.set_mode(mode)
        self._current = None
        self.save_btn.configure(state=tk.DISABLED)
        self.fix_btn.configure(state=tk.DISABLED)

        if mode == "quiz4":
            self._frame_side.pack_forget()
            self._frame_quiz4.pack(fill=tk.X)
            self._btn_quiz4.configure(bg=ACCENT, fg="white")
            self._btn_side.configure(bg=BG2, fg=TEXT_DIM)
            self.ans_num_var.set("─")
            self.ans_text_var.set("")
            self.q_var4.set("等待題目出現…")
            for v in self.opt_vars: v.set("")
        else:
            self._frame_quiz4.pack_forget()
            self._frame_side.pack(fill=tk.X)
            self._btn_side.configure(bg=ACCENT, fg="white")
            self._btn_quiz4.configure(bg=BG2, fg=TEXT_DIM)
            self.ans_ox_var.set("─")
            self.ans_ox_lbl.configure(fg=COL_UNK)
            self.q_vars.set("等待題目出現…")

    def _build_db4(self, f):
        cols = ("question","answer","source")
        self.db4_tree = ttk.Treeview(f, columns=cols, show="headings", height=18)
        self.db4_tree.heading("question", text="題目")
        self.db4_tree.heading("answer",   text="答案")
        self.db4_tree.heading("source",   text="來源")
        self.db4_tree.column("question",  width=220)
        self.db4_tree.column("answer",    width=120)
        self.db4_tree.column("source",    width=80)
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.db4_tree.yview)
        self.db4_tree.configure(yscrollcommand=vsb.set)
        self.db4_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_db4).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_db4).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊列可修改答案）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.db4_tree.bind("<Double-Button-1>", self._edit_db4_entry)
        self._refresh_db4()

    def _build_dbs(self, f):
        cols = ("question","answer")
        self.dbs_tree = ttk.Treeview(f, columns=cols, show="headings", height=18)
        self.dbs_tree.heading("question", text="題目")
        self.dbs_tree.heading("answer",   text="O/X")
        self.dbs_tree.column("question",  width=320)
        self.dbs_tree.column("answer",    width=50, anchor="center")
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.dbs_tree.yview)
        self.dbs_tree.configure(yscrollcommand=vsb.set)
        self.dbs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_dbs).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_dbs).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊列可修改答案）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.dbs_tree.bind("<Double-Button-1>", self._edit_dbs_entry)
        self._refresh_dbs()

    def _build_cfg(self, f):
        self._cfg_vars = {}

        def row(parent, label, key, desc=""):
            r = tk.Frame(parent, bg=BG2); r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self.config.get(key,"")))
            self._cfg_vars[key] = var
            tk.Entry(r, textvariable=var, width=8,
                     bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=4)
            if desc:
                tk.Label(r, text=desc, bg=BG2, fg=TEXT_DIM,
                         font=("Microsoft JhengHei UI",8)).pack(side=tk.LEFT)

        tk.Label(f, text="Claude API Key", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w")
        api_row = tk.Frame(f, bg=BG2); api_row.pack(fill=tk.X, pady=2)
        tk.Label(api_row, text="ANTHROPIC_API_KEY", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
        api_var = tk.StringVar(value=self.config.get("api_key",""))
        self._cfg_vars["api_key"] = api_var
        api_entry = tk.Entry(api_row, textvariable=api_var, width=28, show="*",
                             bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM, relief=tk.FLAT)
        api_entry.pack(side=tk.LEFT, padx=4)
        def _toggle_show(btn=None, entry=api_entry):
            entry.configure(show="" if entry.cget("show")=="*" else "*")
            if btn: btn.configure(text="隱藏" if entry.cget("show")==""  else "顯示")
        show_btn = tk.Button(api_row, text="顯示", bg=BG2, fg=TEXT_DIM, relief=tk.FLAT, padx=4,
                             font=("Microsoft JhengHei UI",8), command=lambda: _toggle_show(show_btn))
        show_btn.pack(side=tk.LEFT)
        tk.Label(f, text="留空則使用 Windows OCR", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="彈窗偵測", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w")
        row(f, "偵測點 X 比例",   "popup_check_x",              "0.0–1.0")
        row(f, "偵測點 Y 比例",   "popup_check_y",              "0.0–1.0")
        row(f, "亮度門檻",        "popup_brightness_threshold", "低於此值=彈窗 (0–255)")
        row(f, "選邊站比對相似度", "match_threshold",            "0.0–1.0（預設 0.72）")

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="題目區域（相對座標）", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w")
        for sub in ["left","top","right","bottom"]:
            r2 = tk.Frame(f, bg=BG2); r2.pack(fill=tk.X, pady=1)
            tk.Label(r2, text=f"  question_region.{sub}", bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
            val = self.config.get("question_region",{}).get(sub, 0)
            var = tk.StringVar(value=str(val))
            self._cfg_vars[f"question_region.{sub}"] = var
            tk.Entry(r2, textvariable=var, width=8,
                     bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        btn_row = tk.Frame(f, bg=BG2); btn_row.pack()
        ttk.Button(btn_row, text="儲存設定",     command=self._apply_cfg).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試亮度",     command=self._test_brightness).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試截圖辨識", command=self._test_recognition).pack(side=tk.LEFT)

    # ── 控制 ──

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.pin_btn.configure(fg="#F1C40F" if self._pinned else "#555577")
        self.root.attributes("-topmost", self._pinned)
        if self._pinned: self.root.deiconify()

    def _toggle_monitor(self):
        if self._thread and self._thread.is_alive():
            self.detector.stop()
            self.start_btn.configure(text="開始監測", bg="#2ECC71")
            self._set_status("已停止")
        else:
            self.detector = GameDetector(
                self.config, self.db4, self.dbs,
                on_detail=lambda m: self.root.after(0, self._add_notif, m, "warn"),
            )
            self.detector.set_mode(self._mode.get())
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
        if not self._pinned: self.root.after(0, self._popup_window)
        self.root.after(0, self._show_result, result)
        # 自動加入題庫（無答案的新題目）
        q = result.get("question", "")
        if q:
            mode = self._mode.get()
            if mode == "quiz4" and not result.get("answer_idx"):
                if not self.db4.lookup(question=q):
                    self.db4.upsert(result.get("phash") or 0, q, None, "",
                                    result.get("options", []))
                    self.root.after(0, self._notify_auto_added, "quiz4")
                    self.root.after(0, self._refresh_db4)
            elif mode == "sidestand" and not result.get("answer"):
                if not self.dbs.lookup(q, threshold=0.9):
                    self.dbs.add(q, None)
                    self.root.after(0, self._notify_auto_added, "sidestand")
                    self.root.after(0, self._refresh_dbs)

    def _add_notif(self, msg, tag="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.notif_log.configure(state=tk.NORMAL)
        self.notif_log.insert("end", f"[{ts}] ", "time")
        self.notif_log.insert("end", msg + "\n", tag)
        self.notif_log.see("end")
        self.notif_log.configure(state=tk.DISABLED)

    def _notify_auto_added(self, mode):
        tab = "四選一題庫" if mode == "quiz4" else "選邊站題庫"
        self.status_lbl.configure(fg="#E67E22")
        self.status_var.set(f"⚠ 未知題目已自動加入「{tab}」（尚無答案），請雙擊補充")
        self._add_notif(f"新題目加入「{tab}」（待填答案）", "warn")
        self.root.after(8000, lambda: self.status_lbl.configure(fg="#666688"))

    def _popup_window(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        if not self._pinned:
            self.root.after(500, lambda: self.root.attributes("-topmost", False))

    def _on_popup_gone(self):
        if not self._pinned: self.root.after(3000, self._auto_hide)

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
        mode = self._mode.get()
        has_q = bool(result.get("question"))
        self.save_btn.configure(state=tk.NORMAL if has_q else tk.DISABLED)

        if mode == "quiz4":
            idx      = result.get("answer_idx")
            ans_text = result.get("answer_text","")
            question = result.get("question","")
            options  = result.get("options",[])
            source   = result.get("source","")

            self.ans_num_var.set(str(idx) if idx else "?")
            self.ans_text_var.set(ans_text)
            self.q_var4.set(question[:50]+("…" if len(question)>50 else ""))
            self.source_var4.set(f"來源：{source}" if source else "")

            for i,(var,color) in enumerate(zip(self.opt_vars, OPT_COLORS)):
                opt  = options[i] if i < len(options) else ""
                star = "★ " if idx == i+1 else "   "
                var.set(f"{star}{i+1}. {opt}")

            for zn in range(1,5):
                fill = ACCENT if idx and zn==idx else "#222240"
                tc   = "#FFFFFF" if idx and zn==idx else "#666688"
                self._map_canvas.itemconfigure(self._map_rects[zn], fill=fill)
                self._map_canvas.itemconfigure(self._map_texts[zn], fill=tc)

            self.fix_btn.configure(state=tk.NORMAL if has_q else tk.DISABLED)

            if idx:
                self._add_notif(f"四選一 → 答案 {idx}. {ans_text[:18]}", "ok")
            elif has_q:
                self._add_notif(f"四選一 → 未知題目：{question[:20]}…", "warn")

        else:
            ans      = result.get("answer")
            question = result.get("question","")
            sim      = result.get("similarity")
            recog    = result.get("recognized","")

            if ans=="O":
                self.ans_ox_var.set("O"); self.ans_ox_lbl.configure(fg=COL_O)
            elif ans=="X":
                self.ans_ox_var.set("X"); self.ans_ox_lbl.configure(fg=COL_X)
            else:
                self.ans_ox_var.set("?"); self.ans_ox_lbl.configure(fg=COL_UNK)

            self.q_vars.set(question[:60]+("…" if len(question)>60 else ""))
            if sim is not None:
                self.source_vars.set(f"相似度 {sim:.0%}　辨識：{recog[:20]}")
            else:
                self.source_vars.set("未找到，可手動存入題庫")

            self.fix_btn.configure(state=tk.DISABLED)

            if ans in ("O", "X"):
                sim_txt = f"（{sim:.0%}）" if sim is not None else ""
                self._add_notif(f"選邊站 → 答案 {ans}{sim_txt}", "ok")
            elif has_q:
                self._add_notif(f"選邊站 → 未找到：{question[:20]}…", "warn")

    # ── 題庫操作 ──

    def _save_to_db(self):
        if not self._current: return
        mode = self._mode.get()
        q    = self._current.get("question","")
        if not q: return

        if mode == "quiz4":
            idx = self._current.get("answer_idx")
            if not idx:
                messagebox.showwarning("提示","請先確認答案（用「修正答案」設定）"); return
            self.db4.upsert(self._current.get("phash") or 0, q, idx,
                            self._current.get("answer_text",""), self._current.get("options",[]))
            self._set_status(f"已存入四選一題庫：{q[:25]}…")
            self._refresh_db4()
        else:
            ans = self._current.get("answer")
            if not ans:
                win = tk.Toplevel(self.root)
                win.title("選擇答案"); win.configure(bg=BG)
                win.attributes("-topmost", True); win.resizable(False, False)
                tk.Label(win, text=f"題目：{q[:40]}", bg=BG, fg=TEXT_NORM,
                         font=("Microsoft JhengHei UI",10), padx=12, pady=8).pack()
                chosen = tk.StringVar()
                br = tk.Frame(win, bg=BG); br.pack(pady=(0,10))
                def pick(v): chosen.set(v); win.destroy()
                tk.Button(br, text="O（正確）", font=("Microsoft JhengHei UI",14,"bold"),
                          bg=COL_O, fg="white", relief=tk.FLAT, padx=14, pady=6,
                          command=lambda: pick("O")).pack(side=tk.LEFT, padx=8)
                tk.Button(br, text="X（錯誤）", font=("Microsoft JhengHei UI",14,"bold"),
                          bg=COL_X, fg="white", relief=tk.FLAT, padx=14, pady=6,
                          command=lambda: pick("X")).pack(side=tk.LEFT, padx=8)
                win.wait_window()
                if not chosen.get(): return
                ans = chosen.get()
                self._current["answer"] = ans
                self._show_result(self._current)
            self.dbs.add(q, ans)
            self._set_status(f"已存入選邊站題庫：{q[:25]}…")
            self._refresh_dbs()

    def _fix_answer(self):
        if not self._current or self._mode.get() != "quiz4": return
        dlg = simpledialog.askstring(
            "修正答案","請輸入正確答案編號（1–4）：",
            initialvalue=str(self._current.get("answer_idx") or ""),
            parent=self.root,
        )
        if dlg and dlg.strip() in ("1","2","3","4"):
            idx  = int(dlg.strip())
            opts = self._current.get("options",[])
            self._current["answer_idx"]  = idx
            self._current["answer_text"] = opts[idx-1] if idx<=len(opts) else ""
            self._show_result(self._current)

    def _refresh_db4(self):
        self.db4_tree.tag_configure("no_ans", foreground="#E67E22")
        for item in self.db4_tree.get_children(): self.db4_tree.delete(item)
        for e in self.db4.entries:
            idx  = e.get("answer_idx")
            t    = e.get("answer_text","")[:15]
            tag  = ("no_ans",) if not idx else ()
            self.db4_tree.insert("","end", tags=tag, values=(
                e.get("question","")[:28],
                f"{idx}. {t}" if idx else "（待填）",
                e.get("source","")[:8]))

    def _refresh_dbs(self):
        self.dbs_tree.tag_configure("no_ans", foreground="#E67E22")
        for item in self.dbs_tree.get_children(): self.dbs_tree.delete(item)
        for e in self.dbs.entries:
            ans = e.get("answer")
            tag = ("no_ans",) if not ans else ()
            self.dbs_tree.insert("","end", tags=tag, values=(
                e.get("question","")[:50], ans or "（待填）"))

    def _edit_db4_entry(self, event):
        sel = self.db4_tree.selection()
        if not sel: return
        idx  = self.db4_tree.index(sel[0])
        entry = self.db4.entries[idx]
        q    = entry.get("question", "")
        opts = entry.get("options", [])

        win = tk.Toplevel(self.root)
        win.title("修改答案"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(False, False)

        tk.Label(win, text=q, bg=BG, fg=TEXT_NORM, wraplength=360,
                 font=("Microsoft JhengHei UI", 10), padx=12, pady=8,
                 justify=tk.LEFT).pack(fill=tk.X)
        tk.Label(win, text="選擇正確答案：", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w", padx=12)

        chosen = tk.IntVar(value=entry.get("answer_idx") or 0)
        btn_frame = tk.Frame(win, bg=BG); btn_frame.pack(padx=12, pady=6, fill=tk.X)
        for i in range(4):
            opt_text = opts[i] if i < len(opts) else f"選項 {i+1}"
            tk.Radiobutton(btn_frame, text=f"{i+1}. {opt_text}",
                           variable=chosen, value=i+1,
                           bg=BG, fg=OPT_COLORS[i], selectcolor="#222240",
                           font=("Microsoft JhengHei UI", 10),
                           activebackground=BG).pack(anchor="w", pady=2)

        def confirm():
            v = chosen.get()
            if v in (1, 2, 3, 4):
                ans_text = opts[v-1] if v <= len(opts) else ""
                self.db4.entries[idx]["answer_idx"]  = v
                self.db4.entries[idx]["answer_text"] = ans_text
                self.db4._save()
                self._refresh_db4()
                self._set_status(f"已更新答案：{q[:20]}… → {v}")
            win.destroy()

        btn_row = tk.Frame(win, bg=BG); btn_row.pack(pady=(4, 10))
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _edit_dbs_entry(self, event):
        sel = self.dbs_tree.selection()
        if not sel: return
        idx   = self.dbs_tree.index(sel[0])
        entry = self.dbs.entries[idx]
        q     = entry.get("question", "")

        win = tk.Toplevel(self.root)
        win.title("修改答案"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(False, False)

        tk.Label(win, text=q, bg=BG, fg=TEXT_NORM, wraplength=360,
                 font=("Microsoft JhengHei UI", 11), padx=12, pady=10,
                 justify=tk.LEFT).pack(fill=tk.X)

        def pick(v):
            self.dbs.entries[idx]["answer"] = v
            self.dbs._save()
            self._refresh_dbs()
            self._set_status(f"已更新答案：{q[:20]}… → {v}")
            win.destroy()

        btn_row = tk.Frame(win, bg=BG); btn_row.pack(pady=(0, 14))
        tk.Button(btn_row, text="O（正確）", font=("Microsoft JhengHei UI", 14, "bold"),
                  bg=COL_O, fg="white", relief=tk.FLAT, padx=16, pady=6,
                  command=lambda: pick("O")).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_row, text="X（錯誤）", font=("Microsoft JhengHei UI", 14, "bold"),
                  bg=COL_X, fg="white", relief=tk.FLAT, padx=16, pady=6,
                  command=lambda: pick("X")).pack(side=tk.LEFT, padx=10)

    def _delete_db4(self):
        sel = self.db4_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆四選一題庫資料？"):
            self.db4.delete(self.db4_tree.index(sel[0]))
            self._refresh_db4()

    def _delete_dbs(self):
        sel = self.dbs_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆選邊站題庫資料？"):
            self.dbs.delete(self.dbs_tree.index(sel[0]))
            self._refresh_dbs()

    def _apply_cfg(self):
        _str_keys = {"api_key"}
        for key, var in self._cfg_vars.items():
            raw = var.get()
            if key in _str_keys:
                self.config[key] = raw; continue
            try:
                val = float(raw)
                if "." in key:
                    rk, sub = key.split(".",1)
                    if rk not in self.config: self.config[rk] = {}
                    self.config[rk][sub] = val
                else:
                    self.config[key] = val
            except ValueError:
                pass
        self.detector.config = self.config
        self._save_config()
        messagebox.showinfo("設定","設定已儲存")

    def _test_brightness(self):
        found = self.detector.find_window()
        if not found: messagebox.showwarning("提示","找不到遊戲視窗"); return
        hwnd, _ = found
        try:
            img, w, h = capture_window(hwnd)
            b = self.detector.sample_brightness(img, w, h)
            messagebox.showinfo("亮度測試",
                f"偵測點目前亮度：{b:.1f}\n門檻：{self.config.get('popup_brightness_threshold',80)}\n\n"
                "彈窗出現時亮度應低於門檻值。")
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _test_recognition(self):
        found = self.detector.find_window()
        if not found: messagebox.showwarning("提示","找不到遊戲視窗，請先開啟遊戲"); return
        hwnd, title = found
        mode = self._mode.get()

        win = tk.Toplevel(self.root)
        win.title("截圖辨識測試"); win.configure(bg=BG)
        win.resizable(False, False); win.attributes("-topmost", True)
        tk.Label(win, text=f"截圖辨識測試（{'四選一' if mode=='quiz4' else '選邊站'}）",
                 bg=BG, fg=ACCENT, font=("Microsoft JhengHei UI",12,"bold")).pack(pady=(8,2))
        status_lbl = tk.Label(win, text="截圖中…", bg=BG, fg=TEXT_DIM,
                              font=("Microsoft JhengHei UI",9))
        status_lbl.pack()
        preview_lbl = tk.Label(win, bg="#111122", relief=tk.SUNKEN, text="（預覽）",
                               fg=TEXT_DIM, font=("Microsoft JhengHei UI",8))
        preview_lbl.pack(padx=12, pady=6, ipadx=4, ipady=4)
        result_txt = tk.Text(win, bg=BG2, fg=TEXT_NORM, height=12, width=50,
                             font=("Microsoft JhengHei UI",10),
                             relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD)
        result_txt.pack(padx=10, pady=(0,10))
        result_txt.tag_configure("ok",   foreground="#2ECC71")
        result_txt.tag_configure("warn", foreground="#E67E22")
        result_txt.tag_configure("dim",  foreground=TEXT_DIM)
        result_txt.tag_configure("head", foreground="#FFAA00",
                                  font=("Microsoft JhengHei UI",10,"bold"))

        def _append(text, tag=None):
            result_txt.configure(state=tk.NORMAL)
            result_txt.insert("end", text, tag) if tag else result_txt.insert("end", text)
            result_txt.configure(state=tk.DISABLED)

        def run():
            try:
                img, w, h  = capture_window(hwnd)
                brightness  = self.detector.sample_brightness(img, w, h)
                threshold   = self.config.get("popup_brightness_threshold", 80)
                popup_ok    = brightness < threshold
                full_img    = self.detector._crop(img, w, h, "popup_full_region")
                pw, ph2     = full_img.size
                scale       = min(380/pw, 1.0)
                preview     = full_img.resize((int(pw*scale), max(1,int(ph2*scale))), Image.Resampling.LANCZOS)
                tk_img      = ImageTk.PhotoImage(preview)

                def update_ui():
                    preview_lbl.configure(image=tk_img, text=""); preview_lbl.image = tk_img
                    _append(f"遊戲：{title}\n","dim")
                    _append(f"亮度：{brightness:.1f}  門檻：{threshold}\n")
                    _append("→ 彈窗已偵測到\n","ok") if popup_ok else _append("→ 未偵測到彈窗\n","warn")
                    if not popup_ok:
                        status_lbl.configure(text="完成（彈窗未出現）"); return

                    def _detail(msg):
                        win.after(0, lambda m=msg: _append(f"  ⚠ {m}\n", "warn"))

                    api_key = self.config.get("api_key","").strip()
                    if mode == "quiz4":
                        if api_key:
                            _append("\nClaude API 辨識中…\n","dim")
                            status_lbl.configure(text="API 辨識中…")
                            q_text, options = claude_read_popup(full_img, api_key, on_detail=_detail)
                            src = "Claude API"
                        else:
                            q_text  = ocr_image(self.detector._crop(img,w,h,"question_region"), on_detail=_detail)
                            opt_img = self.detector._crop(img,w,h,"options_region")
                            options = self.detector._parse_options(ocr_image(opt_img))
                            src = "Windows OCR"
                        _append(f"\n辨識方式：{src}\n","dim")
                        _append("題目：","head"); _append(f"{q_text or '（無法辨識）'}\n")
                        _append("選項：\n","head")
                        for i,opt in enumerate(options[:4]): _append(f"  {i+1}. {opt}\n")
                    else:
                        if api_key:
                            _append("\nClaude API 辨識中…\n","dim")
                            status_lbl.configure(text="API 辨識中…")
                            q_text = claude_read_question(full_img, api_key, on_detail=_detail)
                            src = "Claude API"
                        else:
                            q_text = ocr_image(self.detector._crop(img,w,h,"question_region"), on_detail=_detail)
                            src = "Windows OCR"
                        _append(f"\n辨識方式：{src}\n","dim")
                        _append("題目：","head"); _append(f"{q_text or '（無法辨識）'}\n")
                        if q_text:
                            entry = self.dbs.lookup(q_text, self.config.get("match_threshold",0.72))
                            if entry:
                                _append(f"\n命中！相似度 {entry['similarity']:.0%}  答案：{entry['answer']}\n","ok")
                            else:
                                _append("\n題庫未找到此題\n","warn")

                    status_lbl.configure(text="辨識完成")

                win.after(0, update_ui)
            except Exception as e:
                win.after(0, lambda: status_lbl.configure(text=f"錯誤：{e}"))

        threading.Thread(target=run, daemon=True).start()


def main():
    root = tk.Tk()
    app  = DaxiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

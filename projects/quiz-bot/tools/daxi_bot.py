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
import hashlib
import math
from difflib import SequenceMatcher
import win32gui
import win32ui
import win32process
import win32api
import win32con
from PIL import Image, ImageTk, ImageOps, ImageEnhance

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
COORD_TEMPLATE_FILE = os.path.join(_APP_DIR, "coord_digit_templates.json")
MAP_REF_DIR       = os.path.join(_APP_DIR, "map_refs")

GAME_TITLE_KEYWORDS = ["黃易", "雙龍", "風起", "群俠"]
GAME_TITLE_MIN_MATCHES = 2
NON_GAME_TITLE_KEYWORDS = [
    "輔助", "測試", "Codex", "Claude", "ChatGPT", "Chrome", "Edge",
    "Visual Studio Code", "Windows Terminal", "PowerShell", "檔案總管",
]
NON_GAME_PROCESS_NAMES = {
    "python.exe", "pythonw.exe", "powershell.exe", "windowsterminal.exe",
    "code.exe", "chrome.exe", "msedge.exe", "explorer.exe", "notepad.exe",
}

DEFAULT_CONFIG = {
    "game_install_dir": r"D:\遊戲(非破解)\黃易群俠傳之風起雙龍 日月新空",
    "game_process_names": ["HY2D.exe", "NEW-HEOGame.exe", "NEW-HEOnline.exe"],
    "popup_check_x": 0.45,
    "popup_check_y": 0.10,
    "popup_brightness_threshold": 80,
    "popup_edge_threshold": 35,
    "popup_recognition_cooldown": 2.0,
    "question_region":  {"left": 0.17, "top": 0.12, "right": 0.74, "bottom": 0.27},
    "options_region":   {"left": 0.17, "top": 0.27, "right": 0.74, "bottom": 0.34},
    "popup_full_region":{"left": 0.15, "top": 0.09, "right": 0.76, "bottom": 0.36},
    "map_name_region":  {"left": 0.67, "top": 0.00, "right": 0.82, "bottom": 0.05},
    "coord_region":     {"left": 0.881, "top": 0.0017, "right": 0.9767, "bottom": 0.0345},
    "quiz_map_keywords": [],   # 留空 = 不篩選；填入關鍵字才啟用地圖過濾
    "map_check_interval": 3,   # 地圖名稱重新 OCR 的間隔秒數
    "map_image_match_threshold": 0.78,
    "coord_check_interval": 2.0,
    "coord_template_threshold": 0.34,
    "coord_auto_learn": 1,
    "sidestand_auto_nav": 0,
    "sidestand_nav_max_steps": 12,
    "sidestand_nav_step_wait": 1.2,
    "sidestand_nav_center_x": 0.50,
    "sidestand_nav_center_y": 0.55,
    "sidestand_nav_radius_x": 0.16,
    "sidestand_nav_radius_y": 0.13,
    "sidestand_coord_tolerance": 80,
    "sidestand_o_coord_x": 0,
    "sidestand_o_coord_y": 0,
    "sidestand_x_coord_x": 0,
    "sidestand_x_coord_y": 0,
    "gemini_api_key": "",
    "gemini_model": "gemini-2.0-flash",
    "api_key": "",
    "api_cooldown": 10,
    "api_rate_limit_backoff": 300,
    "match_threshold": 0.72,
    "auto_add_duplicate_threshold": 0.80,
    "window_width": 460,
    "window_height": 460,
}

_OCR_SCRIPT = r"""
import sys, asyncio
sys.stdout.reconfigure(encoding='utf-8')
import winrt.windows.media.ocr as ocr
import winrt.windows.globalization as glob
import winrt.windows.graphics.imaging as wgi
import winrt.windows.storage.streams as wss
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

_OCR_DETAIL_SCRIPT = r"""
import sys, asyncio, json
sys.stdout.reconfigure(encoding='utf-8')
import winrt.windows.media.ocr as ocr
import winrt.windows.globalization as glob
import winrt.windows.graphics.imaging as wgi
import winrt.windows.storage.streams as wss
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
        if not ocr.OcrEngine.is_language_supported(lang):
            continue
        engine = ocr.OcrEngine.try_create_from_language(lang)
        if not engine:
            continue
        result = await engine.recognize_async(bitmap)
        payload = {"text": result.text if result else "", "lines": []}
        if result:
            for line in result.lines:
                words = []
                xs, ys, rs, bs = [], [], [], []
                for word in line.words:
                    rect = word.bounding_rect
                    item = {
                        "text": word.text,
                        "left": rect.x,
                        "top": rect.y,
                        "right": rect.x + rect.width,
                        "bottom": rect.y + rect.height,
                    }
                    words.append(item)
                    xs.append(item["left"]); ys.append(item["top"])
                    rs.append(item["right"]); bs.append(item["bottom"])
                if words:
                    payload["lines"].append({
                        "text": line.text,
                        "left": min(xs),
                        "top": min(ys),
                        "right": max(rs),
                        "bottom": max(bs),
                        "words": words,
                    })
        print(json.dumps(payload, ensure_ascii=False), end='')
        return
    print(json.dumps({"text": "", "lines": []}, ensure_ascii=False), end='')
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

def _window_process_path(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_uint(len(buf))
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return ""
    return ""

def _is_path_under(path, parent):
    if not path or not parent:
        return False
    try:
        path = os.path.normcase(os.path.abspath(path))
        parent = os.path.normcase(os.path.abspath(parent))
        return os.path.commonpath([path, parent]) == parent
    except Exception:
        return False

def is_game_window(hwnd, title=None, config=None):
    title = title if title is not None else win32gui.GetWindowText(hwnd)
    if not title or any(k in title for k in NON_GAME_TITLE_KEYWORDS):
        return False
    proc_path = _window_process_path(hwnd)
    proc_name = os.path.basename(proc_path).lower()
    if proc_name in NON_GAME_PROCESS_NAMES:
        return False
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        if right - left < 640 or bottom - top < 360:
            return False
    except Exception:
        return False
    config = config or {}
    game_dir = (config.get("game_install_dir") or "").strip()
    game_names = {str(n).lower() for n in config.get("game_process_names", []) if str(n).strip()}
    if game_dir:
        return _is_path_under(proc_path, game_dir) and (not game_names or proc_name in game_names)
    matches = sum(1 for k in GAME_TITLE_KEYWORDS if k in title)
    return matches >= GAME_TITLE_MIN_MATCHES

def strip_window_frame_if_present(img):
    """User screenshots often include the white Windows title bar; live capture_window does not."""
    if img.height < 120 or img.width < 320:
        return img, 0
    for y in range(18, min(60, img.height)):
        row = img.crop((0, y, img.width, y + 1)).convert("L")
        avg = sum(row.getdata()) / max(1, img.width)
        if avg < 180:
            return img.crop((0, y, img.width, img.height)), y
    return img, 0

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

def image_similarity(a, b, size=(180, 40)):
    a = ImageOps.autocontrast(a.convert("L").resize(size, Image.Resampling.LANCZOS))
    b = ImageOps.autocontrast(b.convert("L").resize(size, Image.Resampling.LANCZOS))
    pa = list(a.getdata())
    pb = list(b.getdata())
    if not pa or len(pa) != len(pb):
        return 0.0
    diff = sum(abs(x - y) for x, y in zip(pa, pb)) / (len(pa) * 255)
    return max(0.0, min(1.0, 1.0 - diff))

def _safe_ref_name(keyword):
    clean = clean_map_name_text(keyword) or "map"
    digest = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:10]
    return f"{digest}_{clean}.png"

def map_reference_path(keyword):
    return os.path.join(MAP_REF_DIR, _safe_ref_name(keyword))

def load_map_reference(keyword):
    path = map_reference_path(keyword)
    if not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None

def _prepare_ocr_image(pil_img):
    img = pil_img.convert("RGB")
    max_side = max(img.width, img.height)
    if max_side < 900:
        scale = 3 if max_side < 320 else 2
        img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    return img

def _prepare_coord_ocr_image(pil_img):
    img = pil_img.convert("L")
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(2.2)
    scale = max(4, min(10, int(96 / max(1, img.height)) + 1))
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    img = ImageOps.expand(img.convert("RGB"), border=(24, 18), fill=(0, 0, 0))
    return img

def ocr_prepared_image(pil_img, on_detail=None):
    try:
        buf = io.BytesIO()
        pil_img.convert("RGB").save(buf, format="PNG")
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

def ocr_coordinate_image(pil_img, on_detail=None):
    texts = []
    for prepared in (_prepare_coord_ocr_image(pil_img), _prepare_ocr_image(pil_img)):
        text = ocr_prepared_image(prepared, on_detail=on_detail).strip()
        if text and text not in texts:
            texts.append(text)
            if parse_game_coordinates(text) or parse_coordinate_parts(text) != (None, None):
                break
    return " ".join(texts).strip()

def _coord_binary_image(pil_img, size=None):
    img = pil_img.convert("RGB")
    if size:
        img = img.resize(size, Image.Resampling.LANCZOS)
    out = Image.new("L", img.size, 0)
    src = img.load()
    dst = out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = src[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mn >= 135 and mx - mn <= 75:
                dst[x, y] = 255
    return out

def _segment_coord_digits(pil_img):
    bw = _coord_binary_image(pil_img)
    w, h = bw.size
    data = bw.load()
    col_counts = []
    for x in range(w):
        count = 0
        for y in range(h):
            if data[x, y] > 0:
                count += 1
        col_counts.append(count)

    active_min = max(1, int(h * 0.12))
    runs = []
    start = None
    for x, count in enumerate(col_counts):
        if count >= active_min and start is None:
            start = x
        elif count < active_min and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, w - 1))

    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] <= 1:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)

    segments = []
    for x1, x2 in merged:
        ys = [
            y for x in range(x1, x2 + 1)
            for y in range(h)
            if data[x, y] > 0
        ]
        if not ys:
            continue
        y1, y2 = min(ys), max(ys)
        width, height = x2 - x1 + 1, y2 - y1 + 1
        if width < 2 or height < max(6, int(h * 0.35)):
            continue
        # Ignore comma-like punctuation.
        if width <= 3 and height <= int(h * 0.55):
            continue
        pad = 1
        if width >= 16:
            parts = max(2, min(3, round(width / 8.5)))
            step = width / parts
            for idx in range(parts):
                sx1 = int(round(x1 + idx * step))
                sx2 = int(round(x1 + (idx + 1) * step)) - 1
                segments.append(pil_img.crop((
                    max(0, sx1 - pad), max(0, y1 - pad),
                    min(w, sx2 + 1 + pad), min(h, y2 + 1 + pad),
                )))
            continue
        crop = pil_img.crop((
            max(0, x1 - pad), max(0, y1 - pad),
            min(w, x2 + 1 + pad), min(h, y2 + 1 + pad),
        ))
        segments.append(crop)
    return segments

def _coord_template_bits(pil_img, size=(12, 18)):
    bw = _coord_binary_image(pil_img, size=size)
    return "".join("1" if p > 0 else "0" for p in bw.getdata())

def _load_coord_templates():
    if not os.path.exists(COORD_TEMPLATE_FILE):
        return {}
    try:
        with open(COORD_TEMPLATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): [str(v) for v in vals] for k, vals in data.items() if str(k).isdigit()}
    except Exception:
        return {}

def _save_coord_templates(templates):
    clean = {}
    for digit, values in templates.items():
        if not str(digit).isdigit():
            continue
        deduped = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        clean[str(digit)] = deduped[-12:]
    tmp = COORD_TEMPLATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, COORD_TEMPLATE_FILE)

def train_coord_templates(coord_img, coord_text):
    digits = re.sub(r"\D+", "", coord_text or "")
    segments = _segment_coord_digits(coord_img)
    if len(segments) != len(digits):
        return False, f"切出的數字數量不一致：畫面 {len(segments)} 個，輸入 {len(digits)} 個"
    templates = _load_coord_templates()
    for digit, segment in zip(digits, segments):
        templates.setdefault(digit, []).append(_coord_template_bits(segment))
    _save_coord_templates(templates)
    learned = sorted(templates.keys())
    return True, f"已校準 {len(segments)} 個數字；目前已有模板：{', '.join(learned)}"

def read_coord_by_templates(coord_img, threshold=0.34):
    templates = _load_coord_templates()
    if not templates:
        return None, "尚未校準座標模板"
    segments = _segment_coord_digits(coord_img)
    if len(segments) < 6:
        return None, f"模板切字失敗：只找到 {len(segments)} 個數字"

    digits = []
    scores = []
    for segment in segments:
        bits = _coord_template_bits(segment)
        best_digit, best_score = None, 1.0
        for digit, variants in templates.items():
            for tmpl in variants:
                if len(tmpl) != len(bits):
                    continue
                score = sum(a != b for a, b in zip(bits, tmpl)) / len(bits)
                if score < best_score:
                    best_digit, best_score = digit, score
        if best_digit is None or best_score > threshold:
            return None, f"模板無法辨識第 {len(digits)+1} 個數字（分數 {best_score:.2f}）"
        digits.append(best_digit)
        scores.append(best_score)

    raw = "".join(digits)
    if len(raw) >= 8:
        x = int(raw[:4])
        y = int(raw[4:8])
        return (x, y), f"template:{raw} score={sum(scores)/len(scores):.2f}"
    return None, f"模板結果太短：{raw}"

def ocr_image(pil_img, on_detail=None):
    try:
        buf = io.BytesIO()
        _prepare_ocr_image(pil_img).save(buf, format="PNG")
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

_OCR_DETAIL_AVAILABLE = None

def ocr_image_details(pil_img, on_detail=None):
    global _OCR_DETAIL_AVAILABLE
    if _OCR_DETAIL_AVAILABLE is False:
        return {"text": "", "lines": []}
    try:
        buf = io.BytesIO()
        _prepare_ocr_image(pil_img).save(buf, format="PNG")
        proc = subprocess.run(
            [sys.executable, "-c", _OCR_DETAIL_SCRIPT],
            input=buf.getvalue(), capture_output=True, timeout=10,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace").strip()
            if "winrt.windows.foundation.collections" in err:
                _OCR_DETAIL_AVAILABLE = False
                return {"text": "", "lines": []}
            if on_detail:
                on_detail(f"OCR 座標讀取錯誤（returncode={proc.returncode}）：{err[:120]}")
            return {"text": "", "lines": []}
        raw = proc.stdout.decode("utf-8", errors="replace").strip()
        _OCR_DETAIL_AVAILABLE = True
        return json.loads(raw) if raw else {"text": "", "lines": []}
    except Exception as e:
        if on_detail: on_detail(f"OCR 座標例外：{type(e).__name__}: {e}")
        return {"text": "", "lines": []}

def _clean_ocr_text(t):
    cjk = r'一-鿿㐀-䶿'
    t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[{cjk}])', '', t or "")
    t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[，。！？；：、,.?!])', '', t)
    t = re.sub(rf'(?<=[，。！？；：、,.?!])[ \t]+(?=[{cjk}])', '', t)
    t = re.sub(r'剩[餘余]時間.*', '', t)
    t = re.sub(r'[ \t]*\d+[ \t]*秒?\s*$', '', t.strip())
    return t.strip()

_OPT_MARKER_RE = re.compile(
    r'^[\(（;；]?\s*'
    r'([1-4１-４]|[Ⅰ-Ⅳ]|[①-④]|IV|[IiLl]{1,3})'
    r'\s*[\.、:：)）]?\s*'
)
_OPT_INLINE_RE = re.compile(
    r'[\(（;；]?\s*'
    r'([1-4１-４]|[Ⅰ-Ⅳ]|[①-④]|IV|[IiLl]{1,3})'
    r'\s*[\.、:：)）]\s*'
)

def _option_marker_num(text):
    m = _OPT_MARKER_RE.match((text or "").strip())
    if not m:
        return None
    raw = m.group(1)
    table = {
        "1": 1, "１": 1, "①": 1, "Ⅰ": 1,
        "2": 2, "２": 2, "②": 2, "Ⅱ": 2,
        "3": 3, "３": 3, "③": 3, "Ⅲ": 3,
        "4": 4, "４": 4, "④": 4, "Ⅳ": 4,
    }
    if raw in table:
        return table[raw]
    ru = raw.upper().replace("L", "I")
    if ru == "IV":
        return 4
    n = ru.count("I")
    return n if 1 <= n <= 3 else None

def _strip_option_marker(text):
    return _OPT_MARKER_RE.sub("", text or "", count=1).strip()

def _strip_after_first_option_marker(text):
    m = _OPT_INLINE_RE.search(text or "")
    return (text[:m.start()] if m else text).strip()

def _split_embedded_question(text):
    text = text or ""
    m = re.search(r'(以下|下列|哪|何|誰|什麼|甚麼|請問|何者|何種|哪一|哪個).*[？?]', text)
    if not m or m.start() <= 0:
        return _clean_ocr_text(text), ""
    return _clean_ocr_text(text[:m.start()]), _clean_ocr_text(text[m.start():m.end()])

def parse_game_coordinates(text):
    raw = text or ""
    raw = raw.translate(str.maketrans({
        "Ａ": "4", "A": "4", "a": "4",
        "Ｅ": "8", "E": "8", "e": "8",
        "Ｏ": "0", "O": "0", "o": "0",
        "Ｉ": "1", "I": "1", "l": "1",
        "Ｓ": "5", "S": "5", "s": "5",
        "Ｚ": "2", "Z": "2", "z": "2",
        "Ｂ": "8", "B": "8",
        "，": ",", "、": ",", "．": ".", "。": ".",
    }))
    m = re.search(r"(\d{4,5})\D{1,5}(\d{4,5})", raw)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def parse_coordinate_number(text):
    raw = text or ""
    raw = raw.translate(str.maketrans({
        "Ａ": "4", "A": "4", "a": "4",
        "Ｅ": "8", "E": "8", "e": "8",
        "Ｏ": "0", "O": "0", "o": "0",
        "Ｉ": "1", "I": "1", "l": "1",
        "Ｓ": "5", "S": "5", "s": "5",
        "Ｚ": "2", "Z": "2", "z": "2",
        "Ｂ": "8", "B": "8",
    }))
    nums = re.findall(r"\d{3,5}", raw)
    if not nums:
        compact = re.sub(r"\D+", "", raw)
        nums = re.findall(r"\d{3,5}", compact)
    if not nums:
        return None
    return int(max(nums, key=len))

def parse_coordinate_parts(text):
    raw = text or ""
    raw = raw.translate(str.maketrans({
        "Ａ": "4", "A": "4", "a": "4",
        "Ｅ": "8", "E": "8", "e": "8",
        "Ｏ": "0", "O": "0", "o": "0",
        "Ｉ": "1", "I": "1", "l": "1",
        "Ｓ": "5", "S": "5", "s": "5",
        "Ｚ": "2", "Z": "2", "z": "2",
        "Ｂ": "8", "B": "8",
    }))
    nums = re.findall(r"\d{3,5}", raw)
    if len(nums) >= 2:
        x = int(nums[0]) if len(nums[0]) >= 4 else None
        y = int(nums[-1]) if len(nums[-1]) >= 4 else None
        return x, y
    return None, None

def clean_map_name_text(text):
    text = _clean_ocr_text(text or "")
    text = re.sub(r"[「」『』【】\[\]()（）{}<>〈〉《》|｜:：;；,，.。!！?？'\"`~～\s]+", "", text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    return text.strip()

def normalize_map_keywords(keywords):
    normalized = []
    for keyword in keywords or []:
        clean_keyword = clean_map_name_text(keyword)
        if not clean_keyword:
            continue
        normalized.append(clean_keyword)
    return normalized

_QUESTION_CONFUSABLES = str.maketrans({
    "？": "", "?": "", "，": "", ",": "", "。": "", ".": "",
    "：": "", ":": "", "；": "", ";": "", "、": "",
    "（": "", "）": "", "(": "", ")": "", "「": "", "」": "",
    "『": "", "』": "", "【": "", "】": "", "《": "", "》": "",
    "！": "", "!": "", "　": "",
})

def normalize_question_text(text):
    text = _clean_ocr_text(text or "")
    text = re.sub(r"剩[餘余]時間.*", "", text)
    text = re.sub(r"[\(（]?\s*[1-4１-４]\s*[\)）\.、:：].*", "", text)
    text = text.translate(_QUESTION_CONFUSABLES)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    return text.strip()

def question_similarity(a, b):
    a_norm = normalize_question_text(a)
    b_norm = normalize_question_text(b)
    if not a_norm or not b_norm:
        return 0.0
    raw_score = SequenceMatcher(None, a or "", b or "").ratio()
    norm_score = SequenceMatcher(None, a_norm, b_norm).ratio()
    if a_norm in b_norm or b_norm in a_norm:
        contained = min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm))
        norm_score = max(norm_score, contained)
    return max(raw_score, norm_score)

def _option_rows_from_text(text, left=0, top=0):
    text = _clean_ocr_text(text)
    markers = list(_OPT_INLINE_RE.finditer(text))
    if not markers:
        return []
    rows = []
    for i, marker in enumerate(markers):
        num = _option_marker_num(marker.group())
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        opt = text[marker.end():end]
        opt = re.sub(r'[\s;；,，？！。]+$', '', opt).strip()
        if num and opt:
            rows.append({"num": num, "text": opt, "left": float(left), "top": float(top)})
    return rows

def _option_rows_from_ocr_line(line):
    line_text = line.get("text", "")
    words = line.get("words") or []
    markers = []
    for idx, word in enumerate(words):
        num = _option_marker_num(word.get("text", ""))
        if num:
            markers.append((idx, num))

    if markers:
        rows = []
        for marker_pos, (idx, num) in enumerate(markers):
            end_idx = markers[marker_pos + 1][0] if marker_pos + 1 < len(markers) else len(words)
            seg_words = words[idx:end_idx]
            text = _clean_ocr_text(" ".join(w.get("text", "") for w in seg_words))
            opt = re.sub(r'[\s;；,，？！。]+$', '', _strip_option_marker(text)).strip()
            if opt:
                rows.append({
                    "num": num,
                    "text": opt,
                    "left": float(words[idx].get("left", line.get("left", 0))),
                    "top": float(words[idx].get("top", line.get("top", 0))),
                })
        return rows

    rows = _option_rows_from_text(line_text, line.get("left", 0), line.get("top", 0))
    if rows:
        return rows

    text = _clean_ocr_text(line_text)
    num = _option_marker_num(text)
    if not num:
        return []
    opt = re.sub(r'[\s;；,，？！。]+$', '', _strip_option_marker(text)).strip()
    if not opt:
        return []
    return [{
        "num": num,
        "text": opt,
        "left": float(line.get("left", 0)),
        "top": float(line.get("top", 0)),
    }]

def _ocr_parse_quiz_by_layout(full_img, question_img=None, on_detail=None):
    data = ocr_image_details(full_img, on_detail=on_detail)
    lines = data.get("lines", [])
    if not data.get("text") and not lines:
        return "", []

    q_text = ""
    if question_img is not None:
        q_data = ocr_image_details(question_img, on_detail=on_detail)
        q_text = _clean_ocr_text(q_data.get("text", ""))
        q_option_rows = []
        for line in q_data.get("lines", []):
            q_option_rows.extend(_option_rows_from_ocr_line(line))
        if len(q_option_rows) >= 2:
            q_text = _strip_after_first_option_marker(q_text)

    option_rows = []
    for line in lines:
        option_rows.extend(_option_rows_from_ocr_line(line))

    if not option_rows:
        return "", []

    slots = {}
    for row in sorted(option_rows, key=lambda r: (r["num"], r["top"], r["left"])):
        opt_text, embedded_q = _split_embedded_question(row["text"])
        if embedded_q and not q_text:
            q_text = embedded_q
        if opt_text:
            slots.setdefault(row["num"], opt_text)
    options = [slots.get(k, "") for k in range(1, 5)]
    while options and not options[-1]:
        options.pop()

    if not q_text:
        first_top = min(row["top"] for row in option_rows)
        q_lines = [
            _clean_ocr_text(line.get("text", ""))
            for line in sorted(lines, key=lambda ln: (float(ln.get("top", 0)), float(ln.get("left", 0))))
            if float(line.get("bottom", line.get("top", 0))) < first_top - 2
            and not _option_marker_num(line.get("text", ""))
        ]
        q_text = _clean_ocr_text("".join(q_lines))

    return q_text, options[:4]

def ocr_parse_quiz(full_img, question_img=None, on_detail=None):
    """OCR 彈窗圖，分離題目和選項。
    question_img：若提供，獨立辨識題目（避免 2 欄選項佈局干擾讀取順序）。
    回傳 (question_str, [opt1, opt2, opt3, opt4])。"""
    q_by_layout, opts_by_layout = _ocr_parse_quiz_by_layout(full_img, question_img=question_img, on_detail=on_detail)
    if q_by_layout and len([o for o in opts_by_layout if o.strip()]) >= 2:
        return q_by_layout, opts_by_layout

    text = ocr_image(full_img, on_detail=on_detail)
    if not text:
        return "", []

    cjk = r'一-鿿㐀-䶿'
    def _norm(t):
        t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[{cjk}])', '', t)
        t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[，。！？；：、,.])', '', t)
        t = re.sub(rf'(?<=[，。！？；：、,.])[ \t]+(?=[{cjk}])', '', t)
        return t

    text = _norm(text)
    text = re.sub(r'剩[餘余]時間.*', '', text)
    text = re.sub(r'[ \t]*\d+[ \t]*秒?\s*$', '', text.strip())

    _OPT = re.compile(
        r'[\(（;；]?\s*'
        r'(?:[1-4１-４]|[Ⅰ-Ⅳ]|[①-④]|IV|[IiLl]{1,3})'
        r'\s*[\.、:：)）]'
    )

    # 獨立辨識題目（用題目區域裁切圖，避免 2 欄選項讀取順序干擾）
    q_text = ""
    if question_img is not None:
        raw = ocr_image(question_img, on_detail=on_detail)
        if raw:
            cand = _norm(raw.strip())
            cand = re.sub(r'剩[餘余]時間.*', '', cand).strip()
            # 若含 2 個以上選項標記，代表框選範圍涵蓋到選項區，放棄此結果
            if len(_OPT.findall(cand)) < 2:
                q_text = cand

    # 找所有選項標記位置，依序提取標記之間的文字（不受 OCR 讀取順序影響）
    def _marker_to_num(m):
        """從標記匹配文字推算選項編號（1-4），處理 2 欄 OCR 讀取順序錯亂問題。"""
        raw = re.sub(r'[\s\(（;；\)）\.、:：]', '', m.group())
        if raw in ('1', '１'): return 1
        if raw in ('2', '２'): return 2
        if raw in ('3', '３'): return 3
        if raw in ('4', '４'): return 4
        cs = {'①': 1, '②': 2, '③': 3, '④': 4}
        if raw in cs: return cs[raw]
        # 羅馬數字 / 同形字母（I/i/l/L 全當 I）：IV=4，個數決定 1-3
        ru = raw.upper().replace('L', 'I')
        if ru == 'IV': return 4
        n = ru.count('I')
        if 1 <= n <= 3: return n
        return None

    markers = list(_OPT.finditer(text))
    if len(markers) >= 2:
        slots = {}
        for i, m in enumerate(markers[:4]):
            num = _marker_to_num(m)
            start = m.end()
            end = (markers[i+1].start() if i+1 < len(markers) and i+1 < 4 else len(text))
            opt = re.sub(r'[\n\r]+', ' ', text[start:end])  # 2 欄換行合併
            opt = re.sub(r'[\s;；,，？！。]+$', '', opt).strip()
            opt, embedded_q = _split_embedded_question(opt)
            if embedded_q and not q_text:
                q_text = embedded_q
            if not opt:
                continue
            if num and num not in slots:
                slots[num] = opt
            else:
                # 無法推斷編號或重複，按順序填入空位
                for k in range(1, 5):
                    if k not in slots:
                        slots[k] = opt; break

        options = [slots.get(k, '') for k in range(1, 5)]
        while options and not options[-1]:
            options.pop()

        if not q_text:
            before = text[:markers[0].start()].strip()
            if len(before) > 4:
                q_text = before
            else:
                qm = max(text.rfind('？'), text.rfind('?'))
                if qm >= 0:
                    seg_start = 0
                    for mm in _OPT.finditer(text[:qm]):
                        nl = text.rfind('\n', mm.end(), qm)
                        if nl >= 0:
                            seg_start = nl + 1
                    q_cand = _OPT.sub('', text[seg_start:qm+1]).strip()
                    if q_cand:
                        q_text = q_cand

        return q_text, options[:4]

    # fallback：找第一個後面跟著另一個標記的位置切分
    m = None
    for candidate in _OPT.finditer(text):
        if _OPT.search(text[candidate.end():candidate.end()+150]):
            m = candidate
            break
    if not m:
        return q_text or text.strip(), []
    if not q_text:
        q_text = text[:m.start()].strip()
    parts = _OPT.split(text[m.start():])
    options = [re.sub(r'[\s;；,，]+$', '', p).strip() for p in parts if p.strip()][:4]
    return q_text, options

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

def _gemini_image_bytes(pil_img):
    buf = io.BytesIO()
    img = pil_img.convert("RGB")
    if max(img.width, img.height) < 600:
        s = max(2, 600 // max(img.width, img.height))
        img = img.resize((img.width * s, img.height * s), Image.Resampling.LANCZOS)
    img.save(buf, format="PNG")
    return buf.getvalue()

def _api_rate_limit_delay(exc, default_seconds=300):
    text = str(exc)
    if not any(k in text for k in ("429", "RESOURCE_EXHAUSTED", "quota", "Quota", "rate limit", "Rate Limit")):
        return None
    m = re.search(r'retryDelay["\']?\s*[:=]\s*["\']?(\d+)s', text)
    if not m:
        m = re.search(r'retry[_ ]?after["\']?\s*[:=]\s*["\']?(\d+)', text, re.I)
    if m:
        return max(30, min(int(m.group(1)) + 5, 3600))
    return default_seconds

def gemini_read_popup(pil_img, api_key, model="gemini-2.0-flash", on_detail=None, on_rate_limited=None):
    """回傳 (question_str, options_list) — 四選一用。"""
    try:
        from google import genai
        from google.genai import types
        import json as _j
        client = genai.Client(api_key=api_key)
        img_bytes = _gemini_image_bytes(pil_img)
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                types.Part.from_text(text='這是一個武俠遊戲的問答截圖（繁體中文）。請讀出題目和選項，以JSON格式回傳（只輸出JSON）：{"question":"完整題目文字","options":["選項1","選項2","選項3","選項4"]}'),
            ],
        )
        raw  = re.sub(r'^```[a-z]*\n?', '', resp.text.strip()).rstrip('`').strip()
        data = _j.loads(raw)
        q    = data.get("question", "").strip()
        opts = [str(o).strip() for o in data.get("options", [])[:4]]
        while len(opts) < 4: opts.append("")
        return q, opts
    except Exception as e:
        delay = _api_rate_limit_delay(e)
        if delay and on_rate_limited:
            on_rate_limited(delay)
        if on_detail: on_detail(f"Gemini(popup) 錯誤：{type(e).__name__}: {str(e)[:120]}")
        return "", []

def gemini_read_question(pil_img, api_key, model="gemini-2.0-flash", on_detail=None, on_rate_limited=None):
    """回傳 question_str — 選邊站用。"""
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        img_bytes = _gemini_image_bytes(pil_img)
        resp = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                types.Part.from_text(text="這是一個武俠遊戲的問答截圖（繁體中文）。請只輸出題目文字，不要任何選項或說明。"),
            ],
        )
        return resp.text.strip()
    except Exception as e:
        delay = _api_rate_limit_delay(e)
        if delay and on_rate_limited:
            on_rate_limited(delay)
        if on_detail: on_detail(f"Gemini(question) 錯誤：{type(e).__name__}: {str(e)[:120]}")
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

    def lookup(self, phash=None, question=None, threshold=0.85):
        if phash:
            for e in self.entries:
                if e.get("phash") and phash_distance(phash, e["phash"]) < 5:
                    return e
        if question:
            best = self.find_similar(question, threshold=threshold)
            if best:
                return best[0]
        return None

    def find_similar(self, question, threshold=0.80):
        best, best_score = None, 0.0
        for e in self.entries:
            s = question_similarity(question, e.get("question", ""))
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return best, round(best_score, 3)
        return None

    def upsert(self, phash, question, answer_idx, answer_text, options):
        for e in self.entries:
            if e.get("question") == question or question_similarity(question, e.get("question", "")) >= 0.92:
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
            s = question_similarity(question, e["question"])
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return dict(best, similarity=round(best_score, 3))
        return None

    def add(self, question, answer):
        existing = self.lookup(question, threshold=0.80)
        if existing:
            return False
        self.entries.append({"question": question, "answer": answer})
        self._save()
        return True

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
        self._last_recognition_time = 0.0
        self._last_api_ph   = None
        self._last_api_time = 0.0
        self._popup_api_used = False
        self._gemini_block_until = 0.0
        self.hwnd            = None
        self._on_detail       = on_detail or (lambda m: None)
        self._map_ok          = True   # 預設 True，關鍵字空清單時不擋
        self._map_check_time  = 0.0
        self._last_map_text   = ""
        self._map_confirmed_at = 0.0   # 最後一次確認活動場景的時間戳
        self._last_coord_region = None
        self._last_auto_learn_digits = set()

    def set_mode(self, mode):
        self.mode             = mode
        self._popup_on        = False
        self._last_ph         = None
        self._last_recognition_time = 0.0
        self._last_api_ph     = None
        self._last_api_time   = 0.0
        self._popup_api_used = False
        self._gemini_block_until = 0.0
        self._map_ok          = True
        self._map_check_time  = 0.0
        self._last_map_text   = ""
        self._map_confirmed_at = 0.0

    def find_window(self):
        result = []
        def cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd): return
            t = win32gui.GetWindowText(hwnd)
            if is_game_window(hwnd, t, self.config):
                result.append((hwnd, t))
        win32gui.EnumWindows(cb, None)
        return result

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

    def popup_edge_strength(self, img, w, h):
        crop = self._crop(img, w, h, "popup_full_region").convert("L")
        cw, ch = crop.size
        if cw <= 0 or ch < 4:
            return 0.0
        row_means = []
        for y in range(ch):
            row = crop.crop((0, y, cw, y + 1))
            pixels = list(row.getdata())
            row_means.append(sum(pixels) / max(1, len(pixels)))
        edges = [abs(row_means[i] - row_means[i - 1]) for i in range(1, len(row_means))]
        if not edges:
            return 0.0
        top = sorted(edges, reverse=True)[:10]
        return sum(top) / len(top)

    def is_popup_visible(self, img, w, h):
        brightness = self.sample_brightness(img, w, h)
        if brightness >= self.config.get("popup_brightness_threshold", 80):
            return False
        edge = self.popup_edge_strength(img, w, h)
        return edge >= float(self.config.get("popup_edge_threshold", 35))

    def _check_map_name(self, img, w, h):
        """定期 OCR 右上地圖名稱，有關鍵字才允許進入辨識流程。"""
        keywords = self.config.get("quiz_map_keywords", [])
        if not keywords:
            return True  # 未設定關鍵字 → 不篩選
        now = time.time()
        if now - self._map_check_time < self.config.get("map_check_interval", 3):
            return self._map_ok  # 使用快取
        self._map_check_time = now
        map_img = self._crop(img, w, h, "map_name_region")
        clean_keywords = normalize_map_keywords(keywords)
        best_keyword = ""
        best_similarity = 0.0
        has_reference = False
        for keyword in clean_keywords:
            ref_img = load_map_reference(keyword)
            if not ref_img:
                continue
            has_reference = True
            sim = image_similarity(map_img, ref_img)
            if sim > best_similarity:
                best_keyword, best_similarity = keyword, sim
        if has_reference:
            threshold = float(self.config.get("map_image_match_threshold", 0.78))
            matched = best_similarity >= threshold
            in_grace = (now - self._map_confirmed_at) < 20.0
            if matched:
                self._map_confirmed_at = now
            status_text = f"圖片:{best_keyword or '未知'} {best_similarity:.0%}"
            if status_text != self._last_map_text:
                self._last_map_text = status_text
                if matched:
                    self._on_detail(f"地圖圖片：{best_keyword}（相似度 {best_similarity:.0%}，啟動辨識）")
                elif in_grace:
                    self._on_detail(f"地圖圖片：相似度 {best_similarity:.0%}（保護期，維持辨識）")
                else:
                    self._on_detail(f"地圖圖片：相似度 {best_similarity:.0%}（未達門檻，略過）")
            self._map_ok = matched or in_grace
            return self._map_ok

        text = ocr_image(map_img).strip()
        if not text:
            return self._map_ok  # OCR 失敗 → 保持上一次判斷
        clean_text = clean_map_name_text(text)
        matched = any(kw and kw in clean_text for kw in clean_keywords)
        in_grace = (now - self._map_confirmed_at) < 20.0  # 確認後保護 20 秒
        if matched:
            self._map_confirmed_at = now
        if clean_text != self._last_map_text:
            self._last_map_text = clean_text
            if matched:
                self._on_detail(f"地圖：{clean_text[:30]}（活動場景，啟動辨識）")
            elif in_grace:
                self._on_detail(f"地圖：{clean_text[:30]}（保護期，維持辨識）")
            else:
                self._on_detail(f"地圖：{clean_text[:30] or text[:30]}（非活動場景，略過）")
        self._map_ok = matched or in_grace
        return self._map_ok

    def read_coordinates(self, img, w, h, try_fallback_regions=False):
        regions = [self.config.get("coord_region", {})]
        if try_fallback_regions:
            default_region = DEFAULT_CONFIG["coord_region"]
            wider_regions = [
                default_region,
                {"left": 0.875, "top": 0.000, "right": 0.985, "bottom": 0.038},
                {"left": 0.860, "top": 0.000, "right": 0.990, "bottom": 0.045},
                {"left": 0.890, "top": 0.000, "right": 0.995, "bottom": 0.045},
            ]
            for candidate in wider_regions:
                if candidate not in regions:
                    regions.append(candidate)

        last_raw = ""
        for region in regions:
            coord, raw = self._read_coordinates_from_region(img, w, h, region)
            last_raw = raw
            if coord and coord[0] >= 1000 and coord[1] >= 1000:
                self._last_coord_region = region
                return coord, raw
        return None, last_raw

    def _read_coordinates_from_region(self, img, w, h, region):
        x1 = int(region.get("left", 0) * w)
        y1 = int(region.get("top", 0) * h)
        x2 = int(region.get("right", 1) * w)
        y2 = int(region.get("bottom", 1) * h)
        if x2 - x1 < 40 or y2 - y1 < 10:
            return None, f"座標區太小：{x2-x1}x{y2-y1}"
        coord_img = img.crop((x1, y1, x2, y2))

        cw, ch = coord_img.size
        coord, raw = read_coord_by_templates(
            coord_img,
            threshold=float(self.config.get("coord_template_threshold", 0.34)),
        )
        if coord:
            return coord, raw

        text = ocr_coordinate_image(coord_img).strip()
        coord = parse_game_coordinates(text)
        if coord:
            self._maybe_auto_learn_coord_templates(coord_img, coord)
            return coord, text

        x_val, y_val = parse_coordinate_parts(text)
        x_text = text
        y_text = text
        if x_val is not None and y_val is not None:
            coord = (x_val, y_val)
            self._maybe_auto_learn_coord_templates(coord_img, coord)
            return coord, text

        x_val = y_val = None
        known_x, known_y = parse_coordinate_parts(text)
        x_val, y_val = known_x, known_y
        if x_val is None:
            for x_end in (0.52, 0.56, 0.62):
                sample = coord_img.crop((0, 0, max(1, int(cw * x_end)), ch))
                raw = ocr_image(sample).strip()
                val = parse_coordinate_number(raw)
                if val is not None and (x_val is None or val >= 1000):
                    x_text, x_val = raw, val
                if x_val is not None and x_val >= 1000:
                    break
        if y_val is None:
            for y_start in (0.42, 0.38, 0.46):
                sample = coord_img.crop((max(0, int(cw * y_start)), 0, cw, ch))
                raw = ocr_image(sample).strip()
                val = parse_coordinate_number(raw)
                if val is not None and (y_val is None or val >= 1000):
                    y_text, y_val = raw, val
                if y_val is not None and y_val >= 1000:
                    break
        if x_val is not None and y_val is not None:
            coord = (x_val, y_val)
            self._maybe_auto_learn_coord_templates(coord_img, coord)
            return coord, f"x={x_text} y={y_text}"
        return None, text

    def _maybe_auto_learn_coord_templates(self, coord_img, coord):
        if not self.config.get("coord_auto_learn", 1):
            return
        if not coord or coord[0] < 1000 or coord[1] < 1000:
            return
        coord_text = f"{coord[0]},{coord[1]}"
        before = set(_load_coord_templates().keys())
        ok, _ = train_coord_templates(coord_img, coord_text)
        if not ok:
            return
        after = set(_load_coord_templates().keys())
        learned = after - before
        if learned and learned != self._last_auto_learn_digits:
            self._last_auto_learn_digits = learned
            self._on_detail(f"座標模板自動學習：新增數字 {', '.join(sorted(learned))}")

    def _can_call_api(self, ph):
        """同一題目只呼叫一次 API：phash 相近 or 冷卻期內直接跳過。"""
        if self._popup_api_used:
            return False
        cooldown = self.config.get("api_cooldown", 10)
        if self._last_api_ph is not None and phash_distance(ph, self._last_api_ph) < 10:
            return False
        if time.time() - self._last_api_time < cooldown:
            return False
        return True

    def _record_api_call(self, ph):
        self._last_api_ph   = ph
        self._last_api_time = time.time()
        self._popup_api_used = True

    def _gemini_available(self):
        return time.time() >= self._gemini_block_until

    def _block_gemini(self, seconds):
        seconds = int(seconds or self.config.get("api_rate_limit_backoff", 300))
        seconds = max(30, min(seconds, 3600))
        self._gemini_block_until = time.time() + seconds
        self._on_detail(f"Gemini API 已達限額，暫停 {seconds} 秒，改用本機 OCR")

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
        if not self._check_map_name(img, w, h):
            if self._popup_on:
                self._popup_on      = False
                self._last_ph       = None
                self._last_recognition_time = 0.0
                self._last_api_ph   = None
                self._last_api_time = 0.0
                self._popup_api_used = False
            on_status("非活動場景，等待中…")
            return None

        visible = self.is_popup_visible(img, w, h)
        if not visible:
            if self._popup_on:
                self._popup_on      = False
                self._last_ph       = None
                self._last_recognition_time = 0.0
                self._last_api_ph   = None
                self._last_api_time = 0.0
                self._popup_api_used = False
                on_status("等待題目…")
            return None
        if not self._popup_on:
            self._popup_on = True

        q_img = self._crop(img, w, h, "question_region")
        ph    = compute_phash(q_img)
        if ph == 0 or ph == (1 << 64) - 1: return None
        now = time.time()
        cooldown = float(self.config.get("popup_recognition_cooldown", 2.0))
        if self._last_recognition_time and now - self._last_recognition_time < cooldown:
            return None
        if self._last_ph is not None and phash_distance(ph, self._last_ph) < 4: return None
        self._last_ph = ph
        self._last_recognition_time = now
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

        full  = self._crop(img, w, h, "popup_full_region")
        q_img = self._crop(img, w, h, "question_region")
        on_status("OCR 辨識中…")
        q_text, options = ocr_parse_quiz(full, question_img=q_img, on_detail=self._on_detail)

        gemini_key = self.config.get("gemini_api_key", "").strip()
        api_key    = self.config.get("api_key", "").strip()
        if (not q_text or len([o for o in options if o.strip()]) < 2) and (gemini_key or api_key) and self._can_call_api(ph):
            if gemini_key and not q_text and self._gemini_available():
                on_status("Gemini API 辨識中…")
                q_text, options = gemini_read_popup(
                    full, gemini_key,
                    model=self.config.get("gemini_model", "gemini-2.0-flash"),
                    on_detail=self._on_detail,
                    on_rate_limited=self._block_gemini)
            elif gemini_key and not q_text:
                on_status("Gemini 已限速，改用備用辨識…")
            if api_key and not q_text:
                on_status("Claude API 辨識中…")
                q_text, options = claude_read_popup(full, api_key, on_detail=self._on_detail)
            self._record_api_call(ph)
        if not q_text:
            on_status("辨識失敗"); return None
        # 公告 / 結果畫面沒有選項，要求至少 2 個才視為有效題目
        if len([o for o in options if o.strip()]) < 2:
            on_status("非題目畫面（選項不足），跳過"); return None

        entry = self.db4.lookup(question=q_text)
        if entry:
            on_status("題庫命中（文字）")
            return dict(entry, options=options or entry.get("options",[]), source="題庫", phash=ph)

        on_status("題庫未找到")
        return {"question": q_text, "answer_idx": None, "answer_text": "",
                "options": options, "source": "未知", "phash": ph}

    def _process_sidestand(self, img, w, h, q_img, ph, on_status):
        full  = self._crop(img, w, h, "popup_full_region")
        q_img = self._crop(img, w, h, "question_region")
        on_status("OCR 辨識中…")
        q_text, _ = ocr_parse_quiz(full, question_img=q_img, on_detail=self._on_detail)

        gemini_key = self.config.get("gemini_api_key", "").strip()
        api_key    = self.config.get("api_key", "").strip()
        if not q_text and (gemini_key or api_key) and self._can_call_api(ph):
            if gemini_key and not q_text and self._gemini_available():
                on_status("Gemini API 辨識中…")
                q_text = gemini_read_question(
                    full, gemini_key,
                    model=self.config.get("gemini_model", "gemini-2.0-flash"),
                    on_detail=self._on_detail,
                    on_rate_limited=self._block_gemini)
            elif gemini_key and not q_text:
                on_status("Gemini 已限速，改用備用辨識…")
            if api_key and not q_text:
                on_status("Claude API 辨識中…")
                q_text = claude_read_question(full, api_key, on_detail=self._on_detail)
            self._record_api_call(ph)
        if not q_text:
            on_status("辨識失敗"); return None
        # 選邊站題目不一定是疑問句；只要彈窗判定成立，就交給題庫相似度處理。

        threshold = self.config.get("match_threshold", 0.72)
        entry = self.dbs.lookup(q_text, threshold)
        if entry:
            on_status(f"命中（{entry['similarity']:.0%}）")
            return dict(entry, phash=ph, recognized=q_text)

        on_status("題庫未找到此題")
        return {"question": q_text, "answer": None, "phash": ph, "recognized": q_text}

    def run(self, on_result, on_status, on_error, on_popup_gone=None, hwnd=None, title=""):
        self._stop.clear()
        if hwnd is None:
            windows = self.find_window()
            if not windows:
                on_error("找不到遊戲視窗，請確認遊戲已開啟"); return
            hwnd, title = windows[0]
        self.hwnd = hwnd
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
        self.root.resizable(True, True)
        self.root.minsize(420, 360)

        self.config   = self._load_config()
        self.db4      = Quiz4Database(QUIZ4_DB_FILE)
        self.dbs      = SidestandDatabase(SIDESTAND_DB_FILE)
        self.detector = GameDetector(self.config, self.db4, self.dbs)
        self._thread  = None
        self._coord_thread = None
        self._coord_stop = threading.Event()
        self._nav_thread = None
        self._nav_stop = threading.Event()
        self._nav_vectors = {}
        self._last_nav_key = None
        self._current = None
        self._pinned  = False
        self._mode    = tk.StringVar(value="quiz4")

        self._apply_saved_window_size()
        self._build_ui()
        self.root.bind("<Configure>", self._remember_window_size)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
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

    def _apply_saved_window_size(self):
        try:
            width = int(float(self.config.get("window_width", 460)))
            height = int(float(self.config.get("window_height", 460)))
        except Exception:
            width, height = 460, 460
        width = max(420, min(width, 1200))
        height = max(360, min(height, 1000))
        self.root.geometry(f"{width}x{height}")

    def _remember_window_size(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        self.config["window_width"] = self.root.winfo_width()
        self.config["window_height"] = self.root.winfo_height()

    def _on_close(self):
        self.detector.stop()
        self._coord_stop.set()
        self._nav_stop.set()
        self._remember_window_size()
        try:
            self._save_config()
        except Exception:
            pass
        self.root.destroy()

    def _lbl(self, parent, **kw):
        kw.setdefault("bg", parent.cget("bg"))
        return tk.Label(parent, **kw)

    # ── 建構 UI ──

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG2, foreground=TEXT_NORM, bordercolor=BG)
        style.configure("TNotebook",     background=BG)
        style.configure("TNotebook.Tab", background=BG2, foreground=TEXT_NORM, padding=[6,3])
        style.map("TNotebook.Tab",       background=[("selected", BG)])

        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        f_main = tk.Frame(nb, bg=BG,  padx=6, pady=3)
        f_db4  = tk.Frame(nb, bg=BG2)
        f_dbs  = tk.Frame(nb, bg=BG2)
        f_cfg  = tk.Frame(nb, bg=BG2)

        nb.add(f_main, text=" 答題 ")
        nb.add(f_db4,  text=" 四選一題庫 ")
        nb.add(f_dbs,  text=" 選邊站題庫 ")
        nb.add(f_cfg,  text=" 設定 ")

        self._build_main(f_main)
        self._build_db4(f_db4)
        self._build_dbs(f_dbs)
        cfg_body = self._make_scrollable_frame(f_cfg, height=340)
        self._build_cfg(cfg_body)

    def _make_scrollable_frame(self, parent, height=340):
        canvas = tk.Canvas(parent, bg=BG2, highlightthickness=0, height=height)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BG2, padx=8, pady=6)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))

        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return body

    def _build_main(self, f):
        # ── 模式切換 ──
        mode_row = tk.Frame(f, bg=BG)
        mode_row.pack(fill=tk.X, pady=(0, 4))

        self._btn_quiz4 = tk.Button(
            mode_row, text="四選一",
            font=("Microsoft JhengHei UI", 9, "bold"),
            bg=ACCENT, fg="white", activebackground="#C0392B",
            relief=tk.FLAT, padx=12, pady=2,
            command=lambda: self._switch_mode("quiz4"),
        )
        self._btn_quiz4.pack(side=tk.LEFT, padx=(0, 4))

        self._btn_side = tk.Button(
            mode_row, text="選邊站",
            font=("Microsoft JhengHei UI", 9, "bold"),
            bg=BG2, fg=TEXT_DIM, activebackground="#2C3E50",
            relief=tk.FLAT, padx=12, pady=2,
            command=lambda: self._switch_mode("sidestand"),
        )
        self._btn_side.pack(side=tk.LEFT)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=(2, 4))
        self._main_pane = tk.PanedWindow(
            f, orient=tk.VERTICAL, bg=BG, bd=0,
            sashwidth=7, sashrelief=tk.RAISED,
            showhandle=True,
        )
        self._main_pane.pack(fill=tk.BOTH, expand=True)

        answer_pane = tk.Frame(self._main_pane, bg=BG)
        notif_pane = tk.Frame(self._main_pane, bg=BG)
        controls_pane = tk.Frame(self._main_pane, bg=BG)
        self._main_pane.add(answer_pane, minsize=105)
        self._main_pane.add(notif_pane, minsize=55)
        self._main_pane.add(controls_pane, minsize=70)

        # ── 四選一顯示區（左右分欄） ──
        self._frame_quiz4 = tk.Frame(answer_pane, bg=BG)

        self.quiz_result_frame = tk.Frame(
            self._frame_quiz4, bg="#151528",
            highlightthickness=1, highlightbackground="#2E2E4A",
        )
        self.quiz_result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.quiz_answer_line_var = tk.StringVar(value="等待四選一題目")
        self._lbl(self.quiz_result_frame, textvariable=self.quiz_answer_line_var,
                  font=("Microsoft JhengHei UI", 16, "bold"),
                  fg=TEXT_DIM, bg="#151528", anchor="center").pack(fill=tk.X, pady=(8, 2))

        info_row4 = tk.Frame(self.quiz_result_frame, bg="#151528")
        info_row4.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        # 左欄：大號答案數字 + 方位圖
        left4 = tk.Frame(info_row4, bg="#151528")
        left4.pack(side=tk.LEFT, padx=(0, 8), anchor="n")

        self.ans_num_var = tk.StringVar(value="─")
        self._lbl(left4, textvariable=self.ans_num_var,
                  font=("Microsoft JhengHei UI", 72, "bold"),
                  fg=ACCENT, bg="#151528", pady=0).pack()

        self._map_canvas = tk.Canvas(left4, bg="#151528", width=120, height=48, highlightthickness=0)
        self._map_canvas.pack()
        CW, CH, GAP = 52, 20, 4
        _zones = [(0,0,1,"1\n左上"),(1,0,2,"2\n右上"),(0,1,4,"4\n左下"),(1,1,3,"3\n右下")]
        self._map_rects = {}; self._map_texts = {}
        x0, y0 = 4, 2
        for col, row, zn, lbl in _zones:
            x1 = x0 + col*(CW+GAP); y1 = y0 + row*(CH+GAP)
            x2, y2 = x1+CW, y1+CH
            rid = self._map_canvas.create_rectangle(x1,y1,x2,y2, fill="#222240", outline="#444466", width=1)
            tid = self._map_canvas.create_text((x1+x2)//2,(y1+y2)//2, text=lbl,
                                               fill="#666688", font=("Microsoft JhengHei UI",8), justify="center")
            self._map_rects[zn]=rid; self._map_texts[zn]=tid

        # 右欄：答案文字 + 題目 + 來源
        right4 = tk.Frame(info_row4, bg="#151528")
        right4.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n")

        self.ans_text_var = tk.StringVar(value="")
        self._lbl(right4, textvariable=self.ans_text_var,
                  font=("Microsoft JhengHei UI", 14, "bold"),
                  fg="#FFAA00", bg="#151528", anchor="w",
                  wraplength=420).pack(fill=tk.X, pady=(4, 2))

        self.q_var4 = tk.StringVar(value="等待題目出現…")
        self._lbl(right4, textvariable=self.q_var4,
                  font=("Microsoft JhengHei UI", 11), fg=TEXT_NORM, bg="#151528",
                  wraplength=460, justify=tk.LEFT, anchor="w").pack(fill=tk.BOTH, expand=True)

        self.source_var4 = tk.StringVar(value="")
        self._lbl(right4, textvariable=self.source_var4,
                  font=("Microsoft JhengHei UI", 9), fg=TEXT_DIM, bg="#151528", anchor="w").pack(fill=tk.X, pady=(4,0))

        ttk.Separator(self._frame_quiz4, orient="horizontal").pack(fill=tk.X, pady=3)

        # 四個可點擊選項
        self.opt_vars = []
        for i in range(4):
            v = tk.StringVar(value=f"  {i+1}. ")
            self.opt_vars.append(v)
            lbl = self._lbl(self._frame_quiz4, textvariable=v,
                            font=("Microsoft JhengHei UI", 10),
                            fg=OPT_COLORS[i], bg=BG, anchor="w",
                            cursor="hand2")
            lbl.pack(fill=tk.X)
            lbl.bind("<ButtonPress-1>",   lambda e, l=lbl: l.configure(bg="#2A2A4A"))
            lbl.bind("<ButtonRelease-1>", lambda e, l=lbl, idx=i+1: (l.configure(bg=BG), self._click_option(idx)))

        # ── 選邊站顯示區（左右分欄） ──
        self._frame_side = tk.Frame(answer_pane, bg=BG)

        self.side_result_frame = tk.Frame(
            self._frame_side, bg="#151528",
            highlightthickness=1, highlightbackground="#2E2E4A",
        )
        self.side_result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.side_answer_line_var = tk.StringVar(value="等待選邊站題目")
        self._lbl(self.side_result_frame, textvariable=self.side_answer_line_var,
                  font=("Microsoft JhengHei UI", 16, "bold"),
                  fg=TEXT_DIM, bg="#151528", anchor="center").pack(fill=tk.X, pady=(8, 2))

        result_mid = tk.Frame(self.side_result_frame, bg="#151528")
        result_mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        self.ans_ox_var = tk.StringVar(value="─")
        self.ans_ox_lbl = self._lbl(result_mid, textvariable=self.ans_ox_var,
                                    font=("Microsoft JhengHei UI", 72, "bold"),
                                    fg=COL_UNK, bg="#151528", pady=0)
        self.ans_ox_lbl.pack(side=tk.LEFT, padx=(0, 16), fill=tk.Y)

        rights = tk.Frame(result_mid, bg="#151528")
        rights.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n")

        self.q_vars = tk.StringVar(value="等待題目出現…")
        self._lbl(rights, textvariable=self.q_vars,
                  font=("Microsoft JhengHei UI", 12), fg=TEXT_NORM, bg="#151528",
                  wraplength=460, justify=tk.LEFT, anchor="w").pack(fill=tk.BOTH, expand=True, pady=(6, 2))

        self.source_vars = tk.StringVar(value="")
        self._lbl(rights, textvariable=self.source_vars,
                  font=("Microsoft JhengHei UI", 9), fg=TEXT_DIM, bg="#151528", anchor="w").pack(fill=tk.X)

        ttk.Separator(self._frame_side, orient="horizontal").pack(fill=tk.X, pady=3)

        # 快速 O/X 點擊列
        ox_row = tk.Frame(self._frame_side, bg=BG)
        ox_row.pack(fill=tk.X)
        self._ox_o_btn = tk.Label(ox_row, text="O  正確", font=("Microsoft JhengHei UI",14,"bold"),
                                  fg=COL_O, bg=BG2, padx=18, pady=4, cursor="hand2", relief=tk.FLAT)
        self._ox_o_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,4))
        self._ox_o_btn.bind("<ButtonPress-1>",   lambda e: self._ox_o_btn.configure(bg="#1A5C38"))
        self._ox_o_btn.bind("<ButtonRelease-1>", lambda e: (self._ox_o_btn.configure(bg=BG2), self._click_ox("O")))
        self._ox_x_btn = tk.Label(ox_row, text="X  錯誤", font=("Microsoft JhengHei UI",14,"bold"),
                                  fg=COL_X, bg=BG2, padx=18, pady=4, cursor="hand2", relief=tk.FLAT)
        self._ox_x_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self._ox_x_btn.bind("<ButtonPress-1>",   lambda e: self._ox_x_btn.configure(bg="#6B1A1A"))
        self._ox_x_btn.bind("<ButtonRelease-1>", lambda e: (self._ox_x_btn.configure(bg=BG2), self._click_ox("X")))

        # 初始顯示四選一
        self._frame_quiz4.pack(fill=tk.BOTH, expand=True)

        # ── 通知欄 ──
        notif_frame = tk.Frame(notif_pane, bg=BG)
        notif_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 2))
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
        self.notif_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        notif_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.notif_log.tag_configure("warn",  foreground="#E67E22")
        self.notif_log.tag_configure("ok",    foreground="#2ECC71")
        self.notif_log.tag_configure("info",  foreground="#3498DB")
        self.notif_log.tag_configure("dim",   foreground="#555577")
        self.notif_log.tag_configure("time",  foreground="#444466")

        # ── 共用按鈕列 ──
        btn_row = tk.Frame(controls_pane, bg=BG)
        btn_row.pack(fill=tk.X)

        self.start_btn = tk.Button(
            btn_row, text="開始監測",
            font=("Microsoft JhengHei UI", 10),
            bg="#2ECC71", fg="white", activebackground="#27AE60",
            relief=tk.FLAT, padx=12, pady=3,
            command=self._toggle_monitor,
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0,6))

        self.fix_btn = tk.Button(
            btn_row, text="修正答案",
            font=("Microsoft JhengHei UI", 10),
            bg="#8E44AD", fg="white", activebackground="#7D3C98",
            relief=tk.FLAT, padx=10, pady=3,
            command=self._fix_answer, state=tk.DISABLED,
        )
        self.fix_btn.pack(side=tk.LEFT, padx=(0,6))

        self.coord_btn = tk.Button(
            btn_row, text="座標監測",
            font=("Microsoft JhengHei UI", 10),
            bg="#2C3E50", fg=TEXT_NORM, activebackground="#34495E",
            relief=tk.FLAT, padx=10, pady=3,
            command=self._toggle_coord_monitor,
        )
        self.coord_btn.pack(side=tk.LEFT)

        self.pin_btn = tk.Button(
            btn_row, text="📌",
            font=("Segoe UI Emoji", 13),
            bg="#2C3E50", fg="#555577", activebackground="#34495E",
            relief=tk.FLAT, padx=6, pady=3,
            command=self._toggle_pin,
        )
        self.pin_btn.pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(value="就緒，按「開始監測」後會自動尋找遊戲視窗")
        self.status_lbl = self._lbl(controls_pane, textvariable=self.status_var,
                  font=("Microsoft JhengHei UI", 8), fg="#666688", bg=BG,
                  wraplength=360, justify=tk.LEFT, anchor="w")
        self.status_lbl.pack(fill=tk.X, pady=(4,0))

        self.coord_var = tk.StringVar(value="座標：未監測")
        self._lbl(controls_pane, textvariable=self.coord_var,
                  font=("Microsoft JhengHei UI", 9, "bold"), fg="#4ECDC4", bg=BG,
                  anchor="w").pack(fill=tk.X, pady=(2,0))

    def _switch_mode(self, mode):
        self._mode.set(mode)
        self.detector.set_mode(mode)
        self._current = None
        self.fix_btn.configure(state=tk.DISABLED)

        if mode == "quiz4":
            self._frame_side.pack_forget()
            self._frame_quiz4.pack(fill=tk.BOTH, expand=True)
            self._btn_quiz4.configure(bg=ACCENT, fg="white")
            self._btn_side.configure(bg=BG2, fg=TEXT_DIM)
            self.ans_num_var.set("─")
            self.ans_text_var.set("")
            self.quiz_answer_line_var.set("等待四選一題目")
            self.q_var4.set("等待題目出現…")
            for v in self.opt_vars: v.set("")
        else:
            self._frame_quiz4.pack_forget()
            self._frame_side.pack(fill=tk.BOTH, expand=True)
            self._btn_side.configure(bg=ACCENT, fg="white")
            self._btn_quiz4.configure(bg=BG2, fg=TEXT_DIM)
            self.ans_ox_var.set("─")
            self.side_answer_line_var.set("等待選邊站題目")
            self.ans_ox_lbl.configure(fg=COL_UNK)
            self.q_vars.set("等待題目出現…")
            self.source_vars.set("")

    def _build_db4(self, f):
        cols = ("question","answer","source")
        self.db4_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
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
        self.dbs_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
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

        tk.Label(f, text="Google Gemini API Key（優先使用）", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w")
        gm_row = tk.Frame(f, bg=BG2); gm_row.pack(fill=tk.X, pady=2)
        tk.Label(gm_row, text="GEMINI_API_KEY", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
        gm_var = tk.StringVar(value=self.config.get("gemini_api_key",""))
        self._cfg_vars["gemini_api_key"] = gm_var
        gm_entry = tk.Entry(gm_row, textvariable=gm_var, width=28, show="*",
                            bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM, relief=tk.FLAT)
        gm_entry.pack(side=tk.LEFT, padx=4)
        def _toggle_gm(btn=None, entry=gm_entry):
            entry.configure(show="" if entry.cget("show")=="*" else "*")
            if btn: btn.configure(text="隱藏" if entry.cget("show")==""  else "顯示")
        gm_show = tk.Button(gm_row, text="顯示", bg=BG2, fg=TEXT_DIM, relief=tk.FLAT, padx=4,
                            font=("Microsoft JhengHei UI",8), command=lambda: _toggle_gm(gm_show))
        gm_show.pack(side=tk.LEFT)
        model_row = tk.Frame(f, bg=BG2); model_row.pack(fill=tk.X, pady=1)
        tk.Label(model_row, text="  Gemini 模型", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
        gm_model_var = tk.StringVar(value=self.config.get("gemini_model","gemini-2.0-flash"))
        self._cfg_vars["gemini_model"] = gm_model_var
        tk.Entry(model_row, textvariable=gm_model_var, width=20,
                 bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="Claude API Key（備用）", bg=BG2, fg="#888855",
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
        tk.Label(f, text="兩個都留空則使用 Windows OCR", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        tk.Label(f, text="彈窗偵測", bg=BG2, fg=ACCENT,
                 font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w")
        row(f, "偵測點 X 比例",   "popup_check_x",              "0.0–1.0")
        row(f, "偵測點 Y 比例",   "popup_check_y",              "0.0–1.0")
        row(f, "亮度門檻",        "popup_brightness_threshold", "低於此值=彈窗 (0–255)")
        row(f, "彈窗框線門檻",     "popup_edge_threshold",       "越高越嚴格（預設 35）")
        row(f, "辨識冷卻秒數",     "popup_recognition_cooldown", "避免同題重複 OCR")
        row(f, "選邊站比對相似度", "match_threshold",            "0.0–1.0（預設 0.72）")
        row(f, "自動加題防重門檻", "auto_add_duplicate_threshold", "越低越容易視為同題")
        row(f, "座標偵測間隔",     "coord_check_interval",       "秒（預設 1.0）")
        row(f, "座標模板門檻",     "coord_template_threshold",   "越低越嚴格（預設 0.34）")
        row(f, "座標自動學習",     "coord_auto_learn",           "1=開，0=關")
        row(f, "地圖圖片相似門檻", "map_image_match_threshold",  "越高越嚴格（預設 0.78）")
        row(f, "選邊自動導航",     "sidestand_auto_nav",         "1=開，0=關")
        row(f, "選邊抵達容許",     "sidestand_coord_tolerance",  "遊戲座標距離")
        row(f, "O 區座標 X",       "sidestand_o_coord_x",        "遊戲座標")
        row(f, "O 區座標 Y",       "sidestand_o_coord_y",        "遊戲座標")
        row(f, "X 區座標 X",       "sidestand_x_coord_x",        "遊戲座標")
        row(f, "X 區座標 Y",       "sidestand_x_coord_y",        "遊戲座標")
        row(f, "導航最多步數",     "sidestand_nav_max_steps",    "預設 12")
        row(f, "導航步間隔",       "sidestand_nav_step_wait",    "秒")

        def region_block(parent, title, rkey, hint=""):
            tk.Label(parent, text="", bg=BG2).pack()
            hdr = tk.Frame(parent, bg=BG2); hdr.pack(fill=tk.X)
            tk.Label(hdr, text=title, bg=BG2, fg=ACCENT,
                     font=("Microsoft JhengHei UI",10,"bold")).pack(side=tk.LEFT)
            tk.Button(hdr, text="框選", bg="#2C3E50", fg=TEXT_DIM, relief=tk.FLAT,
                      padx=6, pady=0, font=("Microsoft JhengHei UI",8),
                      activebackground="#3D5068",
                      command=lambda k=rkey: self._open_region_selector(k)
                      ).pack(side=tk.LEFT, padx=(8,0))
            if hint:
                tk.Label(parent, text=hint, bg=BG2, fg=TEXT_DIM,
                         font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=4)
            for sub in ["left","top","right","bottom"]:
                rr = tk.Frame(parent, bg=BG2); rr.pack(fill=tk.X, pady=1)
                tk.Label(rr, text=f"  {rkey}.{sub}", bg=BG2, fg=TEXT_NORM,
                         font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
                val = self.config.get(rkey,{}).get(sub, 0)
                var = tk.StringVar(value=str(val))
                self._cfg_vars[f"{rkey}.{sub}"] = var
                tk.Entry(rr, textvariable=var, width=8,
                         bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                         relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        region_block(f, "彈窗完整範圍（OCR 用）", "popup_full_region")
        region_block(f, "題目文字區域", "question_region")
        region_block(f, "右上座標區域", "coord_region",
                     hint="框選右上角角色座標，例如 4248,4024")
        region_block(f, "地圖名稱過濾（右上角）", "map_name_region",
                     hint="設定後只在指定場景啟動辨識；留空關鍵字欄位 = 不過濾")
        kw_row = tk.Frame(f, bg=BG2); kw_row.pack(fill=tk.X, pady=2)
        tk.Label(kw_row, text="  活動關鍵字（逗號分隔）", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
        kw_str = ",".join(self.config.get("quiz_map_keywords", []))
        self._kw_var = tk.StringVar(value=kw_str)
        tk.Entry(kw_row, textvariable=self._kw_var, width=22,
                 bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=4)

        tk.Label(f, text="", bg=BG2).pack()
        btn_row = tk.Frame(f, bg=BG2); btn_row.pack()
        ttk.Button(btn_row, text="儲存設定",       command=self._apply_cfg).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試亮度",       command=self._test_brightness).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試地圖名稱",   command=self._test_map_name).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="校準地圖圖片",   command=self._calibrate_map_image).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試座標",       command=self._test_coordinates).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="校準座標模板",   command=self._calibrate_coord_templates).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="測試截圖辨識",   command=self._test_recognition).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="從截圖檔案辨識", command=self._test_recognition_file).pack(side=tk.LEFT)

    # ── 控制 ──

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.pin_btn.configure(fg="#F1C40F" if self._pinned else "#555577")
        self.root.attributes("-topmost", self._pinned)
        if self._pinned: self.root.deiconify()

    def _pick_window(self, windows):
        """多個遊戲視窗時彈出選擇對話框，回傳 (hwnd, title) 或 None。"""
        if len(windows) == 1:
            return windows[0]
        win = tk.Toplevel(self.root)
        win.title("選擇遊戲視窗"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(False, False)
        tk.Label(win, text="找到多個遊戲視窗，請選擇：", bg=BG, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI", 10)).pack(pady=(12,4), padx=16)
        chosen = [None]
        lb = tk.Listbox(win, bg="#1A1A2E", fg=TEXT_NORM,
                        selectbackground=ACCENT, selectforeground="white",
                        font=("Microsoft JhengHei UI", 10),
                        height=min(len(windows), 8), width=52,
                        relief=tk.FLAT, activestyle="none", borderwidth=0)
        lb.pack(padx=16, pady=4)
        for hwnd_i, t in windows:
            try:
                r = win32gui.GetWindowRect(hwnd_i)
                pos = f"  ({r[0]},{r[1]})"
            except Exception:
                pos = ""
            lb.insert(tk.END, f"  {t}{pos}")
        lb.selection_set(0)
        def ok():
            sel = lb.curselection()
            if sel: chosen[0] = windows[sel[0]]
            win.destroy()
        tk.Button(win, text="確定", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=20, pady=4, font=("Microsoft JhengHei UI", 10),
                  activebackground="#C0392B", command=ok).pack(pady=(4,14))
        win.grab_set()
        win.wait_window()
        return chosen[0]

    def _find_or_pick(self):
        """找遊戲視窗，多個時讓使用者選，回傳 (hwnd, title) 或 None。"""
        windows = self.detector.find_window()
        if not windows:
            messagebox.showwarning("提示", "找不到遊戲視窗，請確認遊戲已開啟")
            return None
        return self._pick_window(windows)

    def _on_detail(self, m):
        """偵測器的 detail 回呼：限速 / 配額錯誤用灰色，其餘用橙色。"""
        tag = "dim" if any(k in m for k in ("429", "RESOURCE_EXHAUSTED", "quota")) else "warn"
        self.root.after(0, self._add_notif, m, tag)

    def _toggle_monitor(self):
        if self._thread and self._thread.is_alive():
            self.detector.stop()
            self.start_btn.configure(text="開始監測", bg="#2ECC71")
            self._set_status("已停止")
        else:
            windows = GameDetector(self.config, self.db4, self.dbs).find_window()
            if not windows:
                messagebox.showerror("錯誤", "找不到遊戲視窗，請確認遊戲已開啟")
                return
            chosen = self._pick_window(windows)
            if not chosen: return
            hwnd, title = chosen
            self.detector = GameDetector(
                self.config, self.db4, self.dbs,
                on_detail=self._on_detail,
            )
            self.detector.set_mode(self._mode.get())
            self.start_btn.configure(text="停止監測", bg="#C0392B")
            self._thread = threading.Thread(
                target=self.detector.run,
                args=(self._on_result, self._set_status, self._on_error),
                kwargs={"on_popup_gone": self._on_popup_gone, "hwnd": hwnd, "title": title},
                daemon=True,
            )
            self._thread.start()

    def _toggle_coord_monitor(self):
        if self._coord_thread and self._coord_thread.is_alive():
            self._coord_stop.set()
            self.coord_btn.configure(text="座標監測", bg="#2C3E50")
            self.coord_var.set("座標：已停止")
            return

        found = self._find_or_pick()
        if not found:
            return
        hwnd, title = found
        self._coord_stop.clear()
        self.coord_btn.configure(text="停止座標", bg="#C0392B")
        self.coord_var.set("座標：讀取中…")
        self._coord_thread = threading.Thread(
            target=self._coord_monitor_loop,
            args=(hwnd, title),
            daemon=True,
        )
        self._coord_thread.start()

    def _coord_monitor_loop(self, hwnd, title):
        detector = GameDetector(self.config, self.db4, self.dbs)
        last = None
        last_msg = None
        interval = max(2.0, float(self.config.get("coord_check_interval", 2.0)))
        while not self._coord_stop.is_set():
            try:
                if not (win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)):
                    self.root.after(0, self.coord_var.set, "座標：遊戲視窗已關閉")
                    break
                img, w, h = capture_window(hwnd)
                coord, raw = detector.read_coordinates(img, w, h)
                if coord:
                    last = coord
                    msg = f"座標：{coord[0]},{coord[1]}  ({title[:12]})"
                elif last:
                    msg = f"座標：{last[0]},{last[1]}  OCR 暫時失敗：{raw[:20] or '空'}"
                else:
                    msg = f"座標：讀取失敗：{raw[:24] or '空'}"
                if msg != last_msg:
                    last_msg = msg
                    self.root.after(0, self.coord_var.set, msg)
            except Exception as e:
                msg = f"座標：錯誤 {e}"
                if msg != last_msg:
                    last_msg = msg
                    self.root.after(0, self.coord_var.set, msg)
            self._coord_stop.wait(interval)

        self.root.after(0, lambda: self.coord_btn.configure(text="座標監測", bg="#2C3E50"))

    def _on_result(self, result):
        self._current = result
        if not self._pinned: self.root.after(0, self._popup_window)
        self.root.after(0, self._show_result, result)
        # 自動加入題庫（無答案的新題目）
        q = result.get("question", "")
        if q:
            mode = self._mode.get()
            dup_threshold = float(self.config.get("auto_add_duplicate_threshold", 0.80))
            if mode == "quiz4" and not result.get("answer_idx"):
                if not self.db4.lookup(question=q, threshold=dup_threshold):
                    self.db4.upsert(result.get("phash") or 0, q, None, "",
                                    result.get("options", []))
                    self.root.after(0, self._notify_auto_added, "quiz4")
                    self.root.after(0, self._refresh_db4)
            elif mode == "sidestand" and not result.get("answer"):
                if not self.dbs.lookup(q, threshold=dup_threshold):
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

        if mode == "quiz4":
            idx      = result.get("answer_idx")
            ans_text = result.get("answer_text","")
            question = result.get("question","")
            options  = result.get("options",[])
            source   = result.get("source","")

            self.ans_num_var.set(str(idx) if idx else "?")
            self.ans_text_var.set(ans_text)
            if idx:
                self.quiz_answer_line_var.set(f"{idx}. {ans_text or '已命中答案'}")
            else:
                self.quiz_answer_line_var.set("尚未命中答案")
            self.q_var4.set(question[:90]+("…" if len(question)>90 else ""))
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
                self.side_answer_line_var.set("O  正確")
            elif ans=="X":
                self.ans_ox_var.set("X"); self.ans_ox_lbl.configure(fg=COL_X)
                self.side_answer_line_var.set("X  錯誤")
            else:
                self.ans_ox_var.set("?"); self.ans_ox_lbl.configure(fg=COL_UNK)
                self.side_answer_line_var.set("尚未命中答案")

            self.q_vars.set(question[:60]+("…" if len(question)>60 else ""))
            if sim is not None:
                self.source_vars.set(f"相似度 {sim:.0%}　辨識：{recog[:48]}")
            else:
                self.source_vars.set("未找到，可手動存入題庫")

            self.fix_btn.configure(state=tk.DISABLED)

            if ans in ("O", "X"):
                sim_txt = f"（{sim:.0%}）" if sim is not None else ""
                self._add_notif(f"選邊站 → 答案 {ans}{sim_txt}", "ok")
                self._maybe_start_sidestand_navigation(ans, result)
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
            if ans:
                self.dbs.add(q, ans)
                self._set_status(f"已存入選邊站題庫：{q[:25]}…")
                self._refresh_dbs()
            else:
                self._set_status("請直接點畫面上的 O / X 設定答案")

    def _click_ox(self, ans):
        """點擊 O/X 按鈕直接設定選邊站答案並存入題庫。"""
        if not self._current or self._mode.get() != "sidestand": return
        q = self._current.get("question", "")
        if not q: return
        self._current["answer"] = ans
        self._show_result(self._current)
        self.dbs.add(q, ans)
        self._set_status(f"答案 {ans} 已記錄：{q[:20]}…")
        self._add_notif(f"選邊站 → 答案確認 {ans}", "ok")
        self._refresh_dbs()

    def _sidestand_target_coord(self, ans):
        prefix = "sidestand_o" if ans == "O" else "sidestand_x"
        try:
            x = int(float(self.config.get(f"{prefix}_coord_x", 0)))
            y = int(float(self.config.get(f"{prefix}_coord_y", 0)))
        except Exception:
            return None
        if x <= 0 or y <= 0:
            return None
        return x, y

    def _read_live_coord(self, hwnd):
        img, w, h = capture_window(hwnd)
        detector = GameDetector(self.config, self.db4, self.dbs)
        coord, raw = detector.read_coordinates(img, w, h)
        return coord, raw

    def _game_click_ratio(self, hwnd, rx, ry):
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        left, top = win32gui.ClientToScreen(hwnd, (0, 0))
        cw, ch = win32gui.GetClientRect(hwnd)[2:4]
        x = int(left + max(0.0, min(1.0, rx)) * cw)
        y = int(top + max(0.0, min(1.0, ry)) * ch)
        if not self._send_screen_click(x, y):
            raise RuntimeError(f"滑鼠點擊送出失敗：{x},{y}")

    def _send_screen_click(self, x, y):
        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        vw = max(1, user32.GetSystemMetrics(78))
        vh = max(1, user32.GetSystemMetrics(79))
        ax = int((x - vx) * 65535 / max(1, vw - 1))
        ay = int((y - vy) * 65535 / max(1, vh - 1))
        flags = win32con.MOUSEEVENTF_ABSOLUTE | win32con.MOUSEEVENTF_MOVE
        try:
            user32.SetCursorPos(int(x), int(y))
        except Exception:
            pass
        time.sleep(0.03)
        user32.mouse_event(flags | win32con.MOUSEEVENTF_LEFTDOWN, ax, ay, 0, 0)
        time.sleep(0.04)
        user32.mouse_event(flags | win32con.MOUSEEVENTF_LEFTUP, ax, ay, 0, 0)
        return True

    def _nav_candidates(self):
        cx = float(self.config.get("sidestand_nav_center_x", 0.50))
        cy = float(self.config.get("sidestand_nav_center_y", 0.55))
        rx = float(self.config.get("sidestand_nav_radius_x", 0.16))
        ry = float(self.config.get("sidestand_nav_radius_y", 0.13))
        return {
            "R": (cx + rx, cy),
            "L": (cx - rx, cy),
            "D": (cx, cy + ry),
            "U": (cx, cy - ry),
            "RD": (cx + rx, cy + ry),
            "RU": (cx + rx, cy - ry),
            "LD": (cx - rx, cy + ry),
            "LU": (cx - rx, cy - ry),
        }

    def _maybe_start_sidestand_navigation(self, ans, result):
        if not self.config.get("sidestand_auto_nav", 0):
            return
        target = self._sidestand_target_coord(ans)
        if not target:
            self._add_notif(f"選邊自動導航未啟動：尚未設定 {ans} 區座標", "warn")
            return
        key = (ans, result.get("phash"), target)
        if key == self._last_nav_key and self._nav_thread and self._nav_thread.is_alive():
            return
        self._last_nav_key = key
        self._nav_stop.set()
        self._nav_stop = threading.Event()
        hwnd = self.detector.hwnd
        if not hwnd or not win32gui.IsWindow(hwnd):
            found = self._find_or_pick()
            if not found:
                return
            hwnd, _ = found
        self._nav_thread = threading.Thread(
            target=self._sidestand_navigation_worker,
            args=(hwnd, ans, target),
            daemon=True,
        )
        self._nav_thread.start()

    def _sidestand_navigation_worker(self, hwnd, ans, target):
        tolerance = float(self.config.get("sidestand_coord_tolerance", 80))
        max_steps = int(float(self.config.get("sidestand_nav_max_steps", 12)))
        wait_s = max(0.4, float(self.config.get("sidestand_nav_step_wait", 1.2)))
        candidates = self._nav_candidates()
        order = list(candidates.keys())
        last_coord = None
        try:
            for step in range(max_steps):
                if self._nav_stop.is_set():
                    return
                coord, raw = self._read_live_coord(hwnd)
                if not coord:
                    self.root.after(0, self._add_notif, f"選邊導航：讀不到座標（{raw[:20] or '空'}）", "warn")
                    return
                dx = target[0] - coord[0]
                dy = target[1] - coord[1]
                dist = math.hypot(dx, dy)
                if dist <= tolerance:
                    self.root.after(0, self._add_notif, f"選邊導航：已到 {ans} 區附近（{coord[0]},{coord[1]}）", "ok")
                    return

                if len(self._nav_vectors) < 4:
                    best_name = order[len(self._nav_vectors)]
                elif self._nav_vectors:
                    best_name = max(
                        self._nav_vectors,
                        key=lambda name: self._nav_vectors[name][0] * dx + self._nav_vectors[name][1] * dy,
                    )
                else:
                    best_name = order[0]

                last_coord = coord
                self._game_click_ratio(hwnd, *candidates[best_name])
                self._nav_stop.wait(wait_s)
                new_coord, _ = self._read_live_coord(hwnd)
                if new_coord and last_coord:
                    vx = new_coord[0] - last_coord[0]
                    vy = new_coord[1] - last_coord[1]
                    if math.hypot(vx, vy) >= 5:
                        old = self._nav_vectors.get(best_name)
                        self._nav_vectors[best_name] = (
                            (old[0] * 0.6 + vx * 0.4) if old else vx,
                            (old[1] * 0.6 + vy * 0.4) if old else vy,
                        )
            self.root.after(0, self._add_notif, f"選邊導航：未在 {max_steps} 步內抵達 {ans} 區", "warn")
        except Exception as e:
            self.root.after(0, self._add_notif, f"選邊導航錯誤：{e}", "warn")

    def _click_option(self, idx):
        """點選選項 label 直接設定答案並存入題庫。"""
        if not self._current or self._mode.get() != "quiz4": return
        opts = self._current.get("options", [])
        self._current["answer_idx"]  = idx
        self._current["answer_text"] = opts[idx-1] if idx <= len(opts) else ""
        self._show_result(self._current)
        q = self._current.get("question", "")
        if q:
            self.db4.upsert(self._current.get("phash") or 0, q, idx,
                            self._current.get("answer_text",""),
                            self._current.get("options",[]))
            ans_t = self._current.get("answer_text","")
            self._set_status(f"答案 {idx} 已記錄：{q[:20]}…")
            self._add_notif(f"四選一 → 答案確認 {idx}. {ans_t[:18]}", "ok")
            self._refresh_db4()

    def _fix_answer(self):
        if not self._current or self._mode.get() != "quiz4": return
        dlg = simpledialog.askstring(
            "修正答案","請輸入正確答案編號（1–4）：",
            initialvalue=str(self._current.get("answer_idx") or ""),
            parent=self.root,
        )
        if dlg and dlg.strip() in ("1","2","3","4"):
            self._click_option(int(dlg.strip()))

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
        _str_keys = {"api_key", "gemini_api_key", "gemini_model"}
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
        # 關鍵字欄位（逗號分隔字串 → list）
        kw_raw = self._kw_var.get().strip()
        self.config["quiz_map_keywords"] = normalize_map_keywords(kw_raw.split(","))
        self._kw_var.set(",".join(self.config["quiz_map_keywords"]))
        self.detector.config = self.config
        self._save_config()
        messagebox.showinfo("設定","設定已儲存")

    def _open_region_selector(self, region_key):
        """截遊戲畫面（或讀截圖檔案），讓使用者拖曳框選區域，自動寫回設定欄位。"""
        img = None
        # 優先用遊戲視窗截圖；找不到時改為開啟截圖檔案
        windows = self.detector.find_window()
        if windows:
            chosen = self._pick_window(windows)
            if chosen:
                hwnd, _ = chosen
                try:
                    img_raw, iw, ih = capture_window(hwnd)
                    img = img_raw
                except Exception as e:
                    messagebox.showerror("錯誤", f"截圖失敗：{e}"); return
        if img is None:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="選擇遊戲截圖檔案",
                filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
            )
            if not path: return
            try:
                img = Image.open(path).convert("RGB")
                iw, ih = img.size
            except Exception as e:
                messagebox.showerror("錯誤", f"無法開啟圖片：{e}"); return

        max_w, max_h = 920, 580
        scale = min(max_w / max(iw, 1), max_h / max(ih, 1), 1.0)
        dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
        display_img = img.resize((dw, dh), Image.Resampling.LANCZOS)

        win = tk.Toplevel(self.root)
        win.title(f"框選區域：{region_key}"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(True, True)
        tk.Label(win, text="拖曳滑鼠框選目標區域，放開後座標自動填入（記得儲存設定）",
                 bg=BG, fg=TEXT_DIM, font=("Microsoft JhengHei UI", 9)).pack(pady=(6, 2))

        canvas = tk.Canvas(win, width=dw, height=dh, bg="#000000",
                           highlightthickness=1, highlightbackground="#444466",
                           cursor="crosshair")
        canvas.pack(padx=8, pady=2)
        tk_img = ImageTk.PhotoImage(display_img)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        canvas._tk_img = tk_img

        # 用藍色虛線畫出目前設定的區域（供參考）
        cur = self.config.get(region_key, {})
        if cur:
            canvas.create_rectangle(
                int(cur.get("left",0)*dw), int(cur.get("top",0)*dh),
                int(cur.get("right",1)*dw), int(cur.get("bottom",1)*dh),
                outline="#3498DB", width=2, dash=(5,4), tags="cur")

        rect_id = [None]
        start   = [0, 0]
        result_lbl = tk.Label(win, text="", bg=BG, fg="#2ECC71",
                              font=("Microsoft JhengHei UI", 9))
        result_lbl.pack(pady=(2, 2))

        def on_press(e):
            start[0], start[1] = e.x, e.y
            if rect_id[0]: canvas.delete(rect_id[0])
            rect_id[0] = canvas.create_rectangle(
                e.x, e.y, e.x, e.y, outline=ACCENT, width=2, tags="sel")

        def on_drag(e):
            if rect_id[0]:
                canvas.coords(rect_id[0], start[0], start[1], e.x, e.y)

        def on_release(e):
            x1 = min(start[0], e.x); y1 = min(start[1], e.y)
            x2 = max(start[0], e.x); y2 = max(start[1], e.y)
            if x2 - x1 < 5 or y2 - y1 < 5: return
            rl = round(x1 / dw, 4); rt = round(y1 / dh, 4)
            rr = round(x2 / dw, 4); rb = round(y2 / dh, 4)
            for sub, val in [("left",rl),("top",rt),("right",rr),("bottom",rb)]:
                k = f"{region_key}.{sub}"
                if k in self._cfg_vars:
                    self._cfg_vars[k].set(str(val))
            result_lbl.configure(
                text=f"left={rl}  top={rt}  right={rr}  bottom={rb}  ✓ 已填入")

        canvas.bind("<ButtonPress-1>",   on_press)
        canvas.bind("<B1-Motion>",       on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        tk.Button(win, text="關閉", bg=BG2, fg=TEXT_DIM, relief=tk.FLAT,
                  padx=16, pady=3, font=("Microsoft JhengHei UI", 9),
                  command=win.destroy).pack(pady=(2, 10))

    def _capture_game_or_pick_file(self, title):
        windows = self.detector.find_window()
        if windows:
            found = self._pick_window(windows)
            if found:
                hwnd, _ = found
                img, w, h = capture_window(hwnd)
                return img, w, h, 0

        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
        )
        if not path:
            return None, 0, 0, 0
        img = Image.open(path).convert("RGB")
        img, frame_top = strip_window_frame_if_present(img)
        w, h = img.size
        return img, w, h, frame_top

    def _calibrate_map_image(self):
        keyword = (self._kw_var.get().split(",")[0] if self._kw_var.get().strip() else "").strip()
        keyword = simpledialog.askstring("校準地圖圖片", "輸入目前地圖名稱關鍵字：", initialvalue=keyword)
        keyword = clean_map_name_text(keyword or "")
        if not keyword:
            return
        try:
            img, w, h, frame_top = self._capture_game_or_pick_file("選擇遊戲截圖（校準地圖圖片）")
            if img is None:
                return
            map_img = self.detector._crop(img, w, h, "map_name_region")
            os.makedirs(MAP_REF_DIR, exist_ok=True)
            path = map_reference_path(keyword)
            map_img.save(path)
            extra = f"\n截圖檔已自動去掉上方標題列 {frame_top}px。" if frame_top else ""
            messagebox.showinfo("校準完成", f"已儲存「{keyword}」地圖圖片參考。{extra}\n\n{path}")
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _calibrate_coord_templates(self):
        coord_text = simpledialog.askstring(
            "校準座標模板",
            "輸入目前右上角座標，例如 4248,4024：",
        )
        if not coord_text:
            return
        digits = re.sub(r"\D+", "", coord_text)
        if len(digits) < 8:
            messagebox.showwarning("提示", "座標至少需要 8 個數字，例如 4248,4024")
            return
        try:
            img, w, h, frame_top = self._capture_game_or_pick_file("選擇遊戲截圖（校準座標模板）")
            if img is None:
                return
            coord_img = self.detector._crop(img, w, h, "coord_region")
            ok, msg = train_coord_templates(coord_img, coord_text)
            if frame_top:
                msg += f"\n截圖檔已自動去掉上方標題列 {frame_top}px。"
            if ok:
                messagebox.showinfo("校準完成", msg)
            else:
                messagebox.showwarning("校準失敗", msg)
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _test_map_name(self):
        img = None
        w = h = 0
        windows = self.detector.find_window()
        if windows:
            found = self._pick_window(windows)
            if found:
                hwnd, _ = found
                try:
                    img, w, h = capture_window(hwnd)
                except Exception as e:
                    messagebox.showerror("錯誤", f"截圖失敗：{e}"); return
        if img is None:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="選擇遊戲截圖（地圖名稱測試）",
                filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
            )
            if not path: return
            try:
                img = Image.open(path).convert("RGB")
                img, frame_top = strip_window_frame_if_present(img)
                w, h = img.size
            except Exception as e:
                messagebox.showerror("錯誤", f"無法開啟圖片：{e}"); return

        win = tk.Toplevel(self.root)
        win.title("地圖名稱偵測測試"); win.configure(bg=BG)
        win.resizable(False, False); win.attributes("-topmost", True)
        tk.Label(win, text="地圖名稱偵測測試", bg=BG, fg=ACCENT,
                 font=("Microsoft JhengHei UI",12,"bold")).pack(pady=(8,2))
        status_lbl = tk.Label(win, text="辨識中…", bg=BG, fg=TEXT_DIM,
                              font=("Microsoft JhengHei UI",9))
        status_lbl.pack()

        # 上：地圖裁切預覽
        tk.Label(win, text="地圖區域（map_name_region）裁切結果：",
                 bg=BG, fg=TEXT_DIM, font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=12)
        map_lbl = tk.Label(win, bg="#111122", relief=tk.SUNKEN,
                           text="（預覽）", fg=TEXT_DIM, font=("Microsoft JhengHei UI",8))
        map_lbl.pack(padx=12, pady=(2,4), ipadx=4, ipady=4)

        # 下：全螢幕截圖＋紅框標示
        tk.Label(win, text="紅框 = 目前設定的地圖區域（全視窗比例）：",
                 bg=BG, fg=TEXT_DIM, font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=12)
        full_lbl = tk.Label(win, bg="#111122", relief=tk.SUNKEN,
                            text="（預覽）", fg=TEXT_DIM, font=("Microsoft JhengHei UI",8))
        full_lbl.pack(padx=12, pady=(2,6), ipadx=4, ipady=4)

        result_lbl = tk.Label(win, text="", bg=BG, fg=TEXT_NORM,
                              font=("Microsoft JhengHei UI",10), wraplength=380, justify=tk.LEFT)
        result_lbl.pack(padx=12, pady=(0,10))

        def run():
            try:
                from PIL import ImageDraw
                region = self.config.get("map_name_region", {})
                x1 = int(region.get("left",  0) * w)
                y1 = int(region.get("top",   0) * h)
                x2 = int(region.get("right", 1) * w)
                y2 = int(region.get("bottom",1) * h)

                # 裁切放大預覽
                map_crop = img.crop((x1, y1, x2, y2))
                mw, mh   = map_crop.size
                scale    = min(360 / max(mw,1), 8.0)   # 最多放大 8x
                map_prev = map_crop.resize(
                    (max(1,int(mw*scale)), max(1,int(mh*scale))),
                    Image.Resampling.NEAREST)
                tk_map = ImageTk.PhotoImage(map_prev)

                # 全視窗縮圖＋紅框
                full_scale = min(380 / max(w,1), 1.0)
                full_prev  = img.resize(
                    (max(1,int(w*full_scale)), max(1,int(h*full_scale))),
                    Image.Resampling.LANCZOS).convert("RGB")
                draw = ImageDraw.Draw(full_prev)
                draw.rectangle(
                    [int(x1*full_scale)-1, int(y1*full_scale)-1,
                     int(x2*full_scale)+1, int(y2*full_scale)+1],
                    outline="red", width=2)
                tk_full = ImageTk.PhotoImage(full_prev)

                # OCR（去除 CJK 字間空格後再比對）
                image_status = ""
                text = ocr_image(map_crop).strip()
                clean_text = clean_map_name_text(text)
                keywords = self.config.get("quiz_map_keywords", [])
                if keywords:
                    clean_keywords = normalize_map_keywords(keywords)
                    best_kw = ""
                    best_sim = 0.0
                    for kw in clean_keywords:
                        ref = load_map_reference(kw)
                        if not ref:
                            continue
                        sim = image_similarity(map_crop, ref)
                        if sim > best_sim:
                            best_kw, best_sim = kw, sim
                    threshold = float(self.config.get("map_image_match_threshold", 0.78))
                    image_matched = bool(best_kw) and best_sim >= threshold
                    image_status = (
                        f"圖片比對：{best_kw or '未校準'} "
                        f"{best_sim:.0%} / 門檻 {threshold:.0%}\n"
                    )
                    matched = image_matched or any(kw and kw in clean_text for kw in clean_keywords)
                    kw_status = ("✓ 符合關鍵字 → 辨識啟動" if matched
                                 else "✗ 不符合關鍵字 → 辨識略過")
                else:
                    clean_keywords = []
                    kw_status = "（關鍵字未設定，不過濾）"

                def update():
                    map_lbl.configure(image=tk_map, text=""); map_lbl.image = tk_map
                    full_lbl.configure(image=tk_full, text=""); full_lbl.image = tk_full
                    result_lbl.configure(
                        text=f"OCR 結果：「{text or '（空，可能區域有誤）'}」\n"
                             f"清理後：「{clean_text or '（空）'}」\n"
                             f"關鍵字：{keywords or '未設定'}\n"
                             f"清理後關鍵字：{clean_keywords or '未設定'}\n"
                             f"{image_status}{kw_status}")
                    status_lbl.configure(text="完成")
                win.after(0, update)
            except Exception as e:
                win.after(0, lambda: status_lbl.configure(text=f"錯誤：{e}"))

        threading.Thread(target=run, daemon=True).start()

    def _test_brightness(self):
        found = self._find_or_pick()
        if not found: return
        hwnd, _ = found
        try:
            img, w, h = capture_window(hwnd)
            b = self.detector.sample_brightness(img, w, h)
            messagebox.showinfo("亮度測試",
                f"偵測點目前亮度：{b:.1f}\n門檻：{self.config.get('popup_brightness_threshold',80)}\n\n"
                "彈窗出現時亮度應低於門檻值。")
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _test_coordinates(self):
        img = None
        w = h = 0
        windows = self.detector.find_window()
        if windows:
            found = self._pick_window(windows)
            if found:
                hwnd, _ = found
                try:
                    img, w, h = capture_window(hwnd)
                except Exception as e:
                    messagebox.showerror("錯誤", f"截圖失敗：{e}"); return
        if img is None:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="選擇遊戲截圖（座標測試）",
                filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
            )
            if not path: return
            try:
                img = Image.open(path).convert("RGB")
                w, h = img.size
            except Exception as e:
                messagebox.showerror("錯誤", f"無法開啟圖片：{e}"); return

        try:
            detector = GameDetector(self.config, self.db4, self.dbs)
            coord, raw = detector.read_coordinates(img, w, h)
            used_fallback = False
            if not coord:
                coord, raw = detector.read_coordinates(img, w, h, try_fallback_regions=True)
                used_fallback = bool(coord)
                if used_fallback and detector._last_coord_region:
                    for sub in ("left", "top", "right", "bottom"):
                        key = f"coord_region.{sub}"
                        val = detector._last_coord_region.get(sub)
                        if key in self._cfg_vars and val is not None:
                            self._cfg_vars[key].set(str(val))
            region = self.config.get("coord_region", {})
            msg = (
                f"OCR 原文：{raw or '（空）'}\n"
                f"解析座標：{coord[0]},{coord[1]}" if coord else
                f"OCR 原文：{raw or '（空）'}\n解析座標：失敗"
            )
            if used_fallback:
                msg += "\n（使用右上候選範圍讀到，已把建議範圍填回設定欄，按「儲存設定」後會比較快）"
            if 'frame_top' in locals() and frame_top:
                msg += f"\n（截圖檔已自動去掉上方標題列 {frame_top}px；正式抓遊戲視窗時本來就不含標題列）"
            msg += (
                "\n\n目前 coord_region："
                f"{region.get('left',0)}, {region.get('top',0)}, "
                f"{region.get('right',1)}, {region.get('bottom',1)}"
            )
            messagebox.showinfo("座標測試", msg)
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def _test_recognition(self):
        found = self._find_or_pick()
        if not found: return
        hwnd, title = found

        def get_img():
            img, w, h = capture_window(hwnd)
            brightness = self.detector.sample_brightness(img, w, h)
            threshold  = self.config.get("popup_brightness_threshold", 80)
            return img, w, h, f"遊戲：{title}", brightness, threshold

        self._open_recognition_dialog(get_img)

    def _test_recognition_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="選擇遊戲截圖",
            filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
        )
        if not path: return
        try:
            img = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("錯誤", f"無法開啟圖片：{e}"); return
        w, h  = img.size
        label = f"檔案：{os.path.basename(path)}"

        def get_img():
            # 檔案模式：不做亮度判斷，直接當彈窗已出現
            return img, w, h, label, None, None

        self._open_recognition_dialog(get_img)

    def _open_recognition_dialog(self, get_img_fn):
        mode = self._mode.get()
        win  = tk.Toplevel(self.root)
        win.title("截圖辨識測試"); win.configure(bg=BG)
        win.resizable(False, False); win.attributes("-topmost", True)
        tk.Label(win, text=f"截圖辨識測試（{'四選一' if mode=='quiz4' else '選邊站'}）",
                 bg=BG, fg=ACCENT, font=("Microsoft JhengHei UI",12,"bold")).pack(pady=(8,2))
        status_lbl = tk.Label(win, text="載入中…", bg=BG, fg=TEXT_DIM,
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
                img, w, h, label, brightness, threshold = get_img_fn()
                full_img = self.detector._crop(img, w, h, "popup_full_region")
                q_img    = self.detector._crop(img, w, h, "question_region")
                pw, ph2  = full_img.size
                scale    = min(380/pw, 1.0)
                preview  = full_img.resize((int(pw*scale), max(1,int(ph2*scale))), Image.Resampling.LANCZOS)
                tk_img   = ImageTk.PhotoImage(preview)

                def update_ui():
                    preview_lbl.configure(image=tk_img, text=""); preview_lbl.image = tk_img
                    _append(f"{label}\n", "dim")

                    # 亮度資訊（即時截圖才有）
                    if brightness is not None:
                        popup_ok = brightness < threshold
                        _append(f"亮度：{brightness:.1f}  門檻：{threshold}\n")
                        _append("→ 彈窗已偵測到\n","ok") if popup_ok else _append("→ 未偵測到彈窗\n","warn")
                        if not popup_ok:
                            status_lbl.configure(text="完成（彈窗未出現）"); return
                    else:
                        _append("→ 檔案模式，直接辨識\n","dim")

                    def _detail(msg):
                        win.after(0, lambda m=msg: _append(f"  ⚠ {m}\n", "warn"))

                    if mode == "quiz4":
                        q_text, options, src = "", [], "Windows OCR"
                        q_text, options = ocr_parse_quiz(full_img, question_img=q_img, on_detail=_detail)
                        _append(f"\n辨識方式：{src}\n","dim")
                        _append("測試模式只跑本機 OCR，不呼叫 Gemini / Claude。\n","dim")
                        _append("題目：","head"); _append(f"{q_text or '（無法辨識）'}\n")
                        _append("選項：\n","head")
                        for i,opt in enumerate(options[:4]): _append(f"  {i+1}. {opt}\n")
                    else:
                        q_text, src = "", "Windows OCR"
                        q_text, _ = ocr_parse_quiz(full_img, question_img=q_img, on_detail=_detail)
                        _append(f"\n辨識方式：{src}\n","dim")
                        _append("測試模式只跑本機 OCR，不呼叫 Gemini / Claude。\n","dim")
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

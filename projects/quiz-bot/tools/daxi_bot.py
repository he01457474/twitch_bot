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
import tempfile
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
    _PROJECT_DIR = _APP_DIR
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_DIR = os.path.dirname(_APP_DIR)

QUIZ4_DB_FILE     = os.path.join(_APP_DIR, "quiz_database.json")
SIDESTAND_DB_FILE = os.path.join(_APP_DIR, "sidestand_database.json")
CFG_FILE          = os.path.join(_APP_DIR, "daxi_config.json")
COORD_TEMPLATE_FILE = os.path.join(_APP_DIR, "coord_digit_templates.json")
MAP_REF_DIR       = os.path.join(_APP_DIR, "map_refs")
OCR_CACHE_DIR     = os.path.join(_APP_DIR, "ocr_cache")
CAPTURE_DIR       = os.path.join(_PROJECT_DIR, "correction_captures")

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
    "popup_brightness_margin": 18,
    "quiz4_popup_frame_threshold": 0.35,
    "quiz4_popup_bottom_frame_threshold": 0.35,
    "quiz4_option_panel_threshold": 0.78,
    "sidestand_popup_frame_threshold": 0.35,
    "popup_recognition_cooldown": 2.0,
    "popup_same_signature_threshold": 0.01,
    "popup_ignore_signature_threshold": 0.002,
    "monitor_idle_interval": 0.70,
    "monitor_active_interval": 0.35,
    "ocr_engine": "windows",  # windows / paddle / auto
    "question_region":  {"left": 0.17, "top": 0.12, "right": 0.74, "bottom": 0.27},
    "options_region":   {"left": 0.17, "top": 0.27, "right": 0.74, "bottom": 0.34},
    "popup_full_region":{"left": 0.15, "top": 0.09, "right": 0.76, "bottom": 0.36},
    "sidestand_question_region":   {"left": 0.17, "top": 0.12, "right": 0.74, "bottom": 0.27},
    "sidestand_popup_full_region": {"left": 0.15, "top": 0.09, "right": 0.76, "bottom": 0.36},
    "map_name_region":  {"left": 0.67, "top": 0.00, "right": 0.82, "bottom": 0.05},
    "coord_region":     {"left": 0.881, "top": 0.0017, "right": 0.9767, "bottom": 0.0345},
    "quiz_map_keywords": [],   # 留空 = 不篩選；填入關鍵字才啟用地圖過濾
    "map_check_interval": 3,   # 地圖名稱重新 OCR 的間隔秒數
    "map_idle_check_interval": 8,
    "map_image_match_threshold": 0.78,
    "map_strict_mode": 1,
    "map_leave_grace_seconds": 5,
    "map_leave_stop_misses": 2,
    "auto_stop_on_map_leave": 1,
    "coord_check_interval": 2.0,
    "coord_template_threshold": 0.34,
    "coord_auto_learn": 1,
    "sidestand_auto_pending": 0,
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
    "allow_paid_api_fallback": 0,
    "api_cooldown": 10,
    "api_rate_limit_backoff": 300,
    "quiz4_match_threshold": 0.78,
    "match_threshold": 0.72,
    "image_question_match_threshold": 0.88,
    "trust_ocr_text_for_pending": 0,
    "auto_add_duplicate_threshold": 0.68,
    "pending_merge_threshold": 0.68,
    "save_pending_captures": 1,
    "save_capture_regions": 1,
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

_PADDLE_OCR_SCRIPT = r"""
import sys, json, tempfile, os
sys.stdout.reconfigure(encoding='utf-8')

def flatten_result(obj, out):
    if obj is None:
        return
    if isinstance(obj, dict):
        texts = obj.get("rec_texts") or obj.get("texts")
        scores = obj.get("rec_scores") or obj.get("scores") or []
        if isinstance(texts, list):
            for i, text in enumerate(texts):
                if text:
                    score = scores[i] if i < len(scores) else 1.0
                    out.append({"text": str(text), "score": float(score)})
            return
        for key in ("text", "label", "transcription"):
            if obj.get(key):
                out.append({"text": str(obj[key]), "score": float(obj.get("score", 1.0))})
                return
        for value in obj.values():
            flatten_result(value, out)
        return
    if isinstance(obj, (list, tuple)):
        if len(obj) >= 2 and isinstance(obj[1], (list, tuple)) and obj[1] and isinstance(obj[1][0], str):
            score = obj[1][1] if len(obj[1]) > 1 else 1.0
            out.append({"text": obj[1][0], "score": float(score)})
            return
        for value in obj:
            flatten_result(value, out)

def make_engine():
    from paddleocr import PaddleOCR
    attempts = [
        dict(
            lang="ch",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        ),
        dict(lang="ch", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False),
        dict(lang="ch", use_angle_cls=False, show_log=False),
        dict(lang="ch"),
    ]
    last = None
    for kwargs in attempts:
        try:
            return PaddleOCR(**kwargs)
        except TypeError as e:
            last = e
    if last:
        raise last
    return PaddleOCR(lang="ch")

def run():
    data = sys.stdin.buffer.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        tmp.write(data)
        tmp.close()
        engine = make_engine()
        if hasattr(engine, "ocr"):
            try:
                result = engine.ocr(tmp.name, cls=False)
            except TypeError:
                result = engine.ocr(tmp.name)
        else:
            result = engine.predict(tmp.name)
        items = []
        flatten_result(result, items)
        text = "\n".join(item["text"] for item in items if item.get("text"))
        print(json.dumps({"text": text, "items": items}, ensure_ascii=False), end="")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

run()
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

def text_mask_similarity(a, b, size=(220, 64)):
    a_mask = _bright_text_mask(a.convert("RGB").resize(size, Image.Resampling.BILINEAR), min_value=125, max_delta=165)
    b_mask = _bright_text_mask(b.convert("RGB").resize(size, Image.Resampling.BILINEAR), min_value=125, max_delta=165)
    pa = [1 if p > 0 else 0 for p in a_mask.getdata()]
    pb = [1 if p > 0 else 0 for p in b_mask.getdata()]
    if not pa or len(pa) != len(pb):
        return 0.0
    a_count = sum(pa)
    b_count = sum(pb)
    if a_count < 18 or b_count < 18:
        return 0.0
    overlap = sum(1 for x, y in zip(pa, pb) if x and y)
    union = a_count + b_count - overlap
    if union <= 0:
        return 0.0
    return max(0.0, min(1.0, overlap / union))

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

def _bright_text_mask(pil_img, min_value=145, max_delta=105):
    img = pil_img.convert("RGB")
    out = Image.new("L", img.size, 0)
    src = img.load()
    dst = out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b = src[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mx >= min_value and mx - mn <= max_delta:
                dst[x, y] = 255
    return out

def _text_signature_bits(pil_img, size=(128, 48)):
    small = pil_img.convert("RGB").resize(size, Image.Resampling.BILINEAR)
    mask = _bright_text_mask(small, min_value=115, max_delta=170)
    return "".join("1" if p > 0 else "0" for p in mask.getdata())

def _signature_distance(a, b):
    if not a or not b or len(a) != len(b):
        return 1.0
    return sum(x != y for x, y in zip(a, b)) / len(a)

def _trim_to_mask(pil_img, mask, pad=2, min_pixels=8):
    bbox = mask.getbbox()
    if not bbox:
        return pil_img
    if sum(1 for p in mask.getdata() if p > 0) < min_pixels:
        return pil_img
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(pil_img.width, x2 + pad)
    y2 = min(pil_img.height, y2 + pad)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return pil_img
    return pil_img.crop((x1, y1, x2, y2))

def _prepare_text_region_ocr_image(pil_img, min_value=145):
    mask = _bright_text_mask(pil_img, min_value=min_value)
    trimmed = _trim_to_mask(pil_img, mask, pad=2)
    text_img = ImageOps.autocontrast(trimmed.convert("RGB"))
    text_img = ImageEnhance.Contrast(text_img).enhance(1.8)
    text_img = ImageEnhance.Sharpness(text_img).enhance(1.6)
    max_side = max(text_img.width, text_img.height)
    scale = 4 if max_side < 220 else 3 if max_side < 500 else 2
    text_img = text_img.resize((text_img.width * scale, text_img.height * scale), Image.Resampling.LANCZOS)
    return ImageOps.expand(text_img, border=(14, 10), fill=(0, 0, 0))

def _prepare_question_ocr_images(pil_img):
    variants = []

    def add(img):
        if img.width < 4 or img.height < 4:
            return
        sig = (img.size, compute_phash(img))
        if any(old_sig == sig for old_sig, _ in variants):
            return
        variants.append((sig, img.convert("RGB")))

    add(_prepare_ocr_image(pil_img))

    gray = ImageOps.autocontrast(pil_img.convert("L"))
    gray = ImageEnhance.Contrast(gray).enhance(2.0)
    gray = ImageEnhance.Sharpness(gray).enhance(1.8)
    scale = max(3, min(6, int(96 / max(1, gray.height)) + 1))
    gray = gray.resize((gray.width * scale, gray.height * scale), Image.Resampling.LANCZOS)
    add(ImageOps.expand(gray.convert("RGB"), border=(18, 12), fill=(0, 0, 0)))

    for min_value in (115, 135):
        mask = _bright_text_mask(pil_img, min_value=min_value, max_delta=150)
        trimmed = _trim_to_mask(pil_img, mask, pad=3, min_pixels=6)
        tmask = _bright_text_mask(trimmed, min_value=min_value, max_delta=150)
        high = Image.new("RGB", trimmed.size, (0, 0, 0))
        src = trimmed.convert("RGB").load()
        dst = high.load()
        mpx = tmask.load()
        for y in range(trimmed.height):
            for x in range(trimmed.width):
                if mpx[x, y] > 0:
                    r, g, b = src[x, y]
                    mx = max(r, g, b)
                    dst[x, y] = (mx, mx, mx)
        scale = max(4, min(8, int(110 / max(1, high.height)) + 1))
        high = high.resize((high.width * scale, high.height * scale), Image.Resampling.LANCZOS)
        add(ImageOps.expand(high, border=(22, 14), fill=(0, 0, 0)))

    add(_prepare_text_region_ocr_image(pil_img, min_value=120))
    return [img for _, img in variants]

def _prepare_paddle_question_ocr_images(pil_img):
    variants = []

    def add(img):
        if img.width < 4 or img.height < 4:
            return
        sig = (img.size, compute_phash(img))
        if any(old_sig == sig for old_sig, _ in variants):
            return
        variants.append((sig, img.convert("RGB")))

    for min_value in (135, 120, 115):
        mask = _bright_text_mask(pil_img, min_value=min_value, max_delta=150)
        trimmed = _trim_to_mask(pil_img, mask, pad=3, min_pixels=6)
        tmask = _bright_text_mask(trimmed, min_value=min_value, max_delta=150)
        high = Image.new("RGB", trimmed.size, (0, 0, 0))
        src = trimmed.convert("RGB").load()
        dst = high.load()
        mpx = tmask.load()
        for y in range(trimmed.height):
            for x in range(trimmed.width):
                if mpx[x, y] > 0:
                    r, g, b = src[x, y]
                    mx = max(r, g, b)
                    dst[x, y] = (mx, mx, mx)
        scale = max(4, min(8, int(110 / max(1, high.height)) + 1))
        high = high.resize((high.width * scale, high.height * scale), Image.Resampling.LANCZOS)
        add(ImageOps.expand(high, border=(22, 14), fill=(0, 0, 0)))

    add(_prepare_text_region_ocr_image(pil_img, min_value=120))
    add(_prepare_ocr_image(pil_img))
    return [img for _, img in variants]

def ocr_map_name_image(pil_img, on_detail=None):
    texts = []
    for prepared in (
        _prepare_text_region_ocr_image(pil_img, min_value=135),
        _prepare_ocr_image(_trim_to_mask(pil_img, _bright_text_mask(pil_img, min_value=135), pad=2)),
    ):
        text = ocr_prepared_image(prepared, on_detail=on_detail).strip()
        clean = clean_map_name_text(text)
        if clean and clean not in texts:
            texts.append(clean)
    if not texts:
        return ""
    cjk_texts = [t for t in texts if re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", t)]
    best = max(cjk_texts or texts, key=len)
    if len(best) < 2 and not re.search(r"[\u4e00-\u9fff\u3400-\u4dbf]", best):
        return ""
    return best

def _prepare_coord_ocr_image(pil_img):
    mask = _bright_text_mask(pil_img, min_value=135, max_delta=85)
    pil_img = _trim_to_mask(pil_img, mask, pad=2, min_pixels=10)
    img = pil_img.convert("L")
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(2.2)
    scale = max(4, min(10, int(96 / max(1, img.height)) + 1))
    img = img.resize((img.width * scale, img.height * scale), Image.Resampling.LANCZOS)
    img = ImageOps.expand(img.convert("RGB"), border=(24, 18), fill=(0, 0, 0))
    return img

_OCR_ENGINE = "auto"
_PADDLE_OCR_AVAILABLE = None
_PADDLE_OCR_WARNED = False
_PADDLE_OCR_ENGINE = None
_OCR_TEXT_CACHE = {}

def set_ocr_engine(engine):
    global _OCR_ENGINE
    engine = str(engine or "auto").strip().lower()
    _OCR_ENGINE = engine if engine in ("auto", "paddle", "windows") else "auto"

def ocr_engine_label():
    if _OCR_ENGINE == "auto":
        if _PADDLE_OCR_AVAILABLE is True:
            return "auto（PaddleOCR）"
        if _PADDLE_OCR_AVAILABLE is False:
            return "auto（Windows OCR 備援）"
    return _OCR_ENGINE

def _prepare_paddle_env():
    os.makedirs(OCR_CACHE_DIR, exist_ok=True)
    updates = {
        "HOME": OCR_CACHE_DIR,
        "USERPROFILE": OCR_CACHE_DIR,
        "PADDLE_HOME": os.path.join(OCR_CACHE_DIR, "paddle"),
        "PADDLEOCR_HOME": os.path.join(OCR_CACHE_DIR, "paddleocr"),
        "XDG_CACHE_HOME": OCR_CACHE_DIR,
        "HF_HOME": os.path.join(OCR_CACHE_DIR, "huggingface"),
        "MODELSCOPE_CACHE": os.path.join(OCR_CACHE_DIR, "modelscope"),
        "FLAGS_use_mkldnn": "0",
        "PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT": "0",
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
    }
    for key, value in updates.items():
        os.environ[key] = value

def _flatten_paddle_result(obj, out):
    if obj is None:
        return
    if isinstance(obj, dict):
        texts = obj.get("rec_texts") or obj.get("texts")
        scores = obj.get("rec_scores") or obj.get("scores") or []
        if isinstance(texts, list):
            for i, text in enumerate(texts):
                if text:
                    score = scores[i] if i < len(scores) else 1.0
                    out.append({"text": str(text), "score": float(score)})
            return
        for key in ("text", "label", "transcription"):
            if obj.get(key):
                out.append({"text": str(obj[key]), "score": float(obj.get("score", 1.0))})
                return
        for value in obj.values():
            _flatten_paddle_result(value, out)
        return
    if isinstance(obj, (list, tuple)):
        if len(obj) >= 2 and isinstance(obj[1], (list, tuple)) and obj[1] and isinstance(obj[1][0], str):
            score = obj[1][1] if len(obj[1]) > 1 else 1.0
            out.append({"text": obj[1][0], "score": float(score)})
            return
        for value in obj:
            _flatten_paddle_result(value, out)

def _get_paddle_engine():
    global _PADDLE_OCR_ENGINE
    if _PADDLE_OCR_ENGINE is not None:
        return _PADDLE_OCR_ENGINE
    _prepare_paddle_env()
    from paddleocr import PaddleOCR
    attempts = [
        dict(
            lang="ch",
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="PP-OCRv5_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        ),
        dict(lang="ch", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False),
        dict(lang="ch", use_angle_cls=False, show_log=False),
        dict(lang="ch"),
    ]
    last = None
    for kwargs in attempts:
        try:
            _PADDLE_OCR_ENGINE = PaddleOCR(**kwargs)
            return _PADDLE_OCR_ENGINE
        except TypeError as e:
            last = e
    if last:
        raise last
    _PADDLE_OCR_ENGINE = PaddleOCR(lang="ch")
    return _PADDLE_OCR_ENGINE

def _run_windows_ocr(pil_img, on_detail=None):
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

def _run_paddle_ocr(pil_img, on_detail=None):
    global _PADDLE_OCR_AVAILABLE, _PADDLE_OCR_WARNED
    if _PADDLE_OCR_AVAILABLE is False:
        return ""
    try:
        engine = _get_paddle_engine()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        try:
            pil_img.convert("RGB").save(tmp, format="PNG")
            tmp.close()
            if hasattr(engine, "ocr"):
                try:
                    result = engine.ocr(tmp.name, cls=False)
                except TypeError:
                    result = engine.ocr(tmp.name)
            else:
                result = engine.predict(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        items = []
        _flatten_paddle_result(result, items)
        text = "\n".join(item["text"] for item in items if item.get("text")).strip()
        _PADDLE_OCR_AVAILABLE = True
        return text
    except Exception as e:
        _PADDLE_OCR_AVAILABLE = False
        if on_detail and not _PADDLE_OCR_WARNED:
            on_detail(f"PaddleOCR 例外，已改用 Windows OCR：{type(e).__name__}: {e}")
            _PADDLE_OCR_WARNED = True
        return ""

def ocr_prepared_image(pil_img, on_detail=None):
    cache_key = (_OCR_ENGINE, pil_img.size, compute_phash(pil_img))
    if cache_key in _OCR_TEXT_CACHE:
        return _OCR_TEXT_CACHE[cache_key]
    engine = _OCR_ENGINE
    if engine in ("auto", "paddle"):
        text = _run_paddle_ocr(pil_img, on_detail=on_detail)
        if text or engine == "paddle":
            _OCR_TEXT_CACHE[cache_key] = text
            if len(_OCR_TEXT_CACHE) > 128:
                _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
            return text
    text = _run_windows_ocr(pil_img, on_detail=on_detail)
    _OCR_TEXT_CACHE[cache_key] = text
    if len(_OCR_TEXT_CACHE) > 128:
        _OCR_TEXT_CACHE.pop(next(iter(_OCR_TEXT_CACHE)))
    return text

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
    mask = _bright_text_mask(pil_img, min_value=135, max_delta=85)
    pil_img = _trim_to_mask(pil_img, mask, pad=1, min_pixels=10)
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
    mask = _bright_text_mask(pil_img, min_value=135, max_delta=85)
    pil_img = _trim_to_mask(pil_img, mask, pad=1, min_pixels=2)
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
    return ocr_prepared_image(_prepare_ocr_image(pil_img), on_detail=on_detail)

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

def _question_candidate_score(text):
    clean = clean_question_candidate(text)
    norm = normalize_question_text(clean)
    if not norm:
        return 0.0
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", norm))
    digit_count = len(re.findall(r"\d", norm))
    operator_count = len(re.findall(r"[+\-*/=><]", norm))
    score = min(40, len(norm)) + cjk_count * 1.5 + digit_count * 0.5 + operator_count * 1.0
    if _QUESTION_CUE_RE.search(clean):
        score += 8
    if "？" in clean or "?" in clean:
        score += 6
    if re.search(r"(以下|下列|哪|何|請問|是否|是不是)", clean):
        score += 5
    if len(norm) < 4:
        score -= 20
    if _looks_like_nameplate_text(clean):
        score -= 35
    if _is_question_title_line(clean):
        score -= 35
    if len(_OPT_MARKER_RE.findall(clean)) >= 2 or len(_OPT_INLINE_RE.findall(clean)) >= 2:
        score -= 25
    if re.search(r"(剩\s*[餘余]?時間|倒\s*數|\d{1,3}\s*秒)", clean):
        score -= 15
    symbol_count = len(re.findall(r"[^\w\u4e00-\u9fff\u3400-\u4dbf\s+\-*/=><？?，,。.:：]", clean))
    if symbol_count > max(2, len(clean) // 5):
        score -= symbol_count * 2
    return max(0.0, score)

def ocr_question_image(pil_img, on_detail=None, high_precision=False):
    candidates = []
    prepared_images = (
        _prepare_paddle_question_ocr_images(pil_img)
        if _OCR_ENGINE in ("auto", "paddle") and _PADDLE_OCR_AVAILABLE is not False
        else _prepare_question_ocr_images(pil_img)
    )
    fast_threshold = 35 if _OCR_ENGINE in ("auto", "paddle") and _PADDLE_OCR_AVAILABLE is not False else 50
    for idx, prepared in enumerate(prepared_images, start=1):
        raw = ocr_prepared_image(prepared, on_detail=on_detail)
        clean = clean_question_candidate(raw)
        score = _question_candidate_score(clean)
        if clean and score >= 12:
            if not high_precision and idx == 1 and score >= fast_threshold:
                return clean
            candidates.append((score, len(normalize_question_text(clean)), idx, clean))
            if not high_precision and score >= fast_threshold:
                break
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    best_score, _, best_idx, best_text = candidates[0]
    if on_detail and best_idx > 1:
        on_detail(f"題目 OCR 使用第 {best_idx} 種清晰化版本（分數 {best_score:.0f}）")
    return best_text

def _clean_ocr_text(t):
    cjk = r'一-鿿㐀-䶿'
    t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[{cjk}])', '', t or "")
    t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[，。！？；：、,.?!])', '', t)
    t = re.sub(rf'(?<=[，。！？；：、,.?!])[ \t]+(?=[{cjk}])', '', t)
    return t.strip()

_NAMEPLATE_TITLE_PATTERN = (
    r"初出茅廬|小有名氣|聲名鵲起|聲聞天下|聲聞天|名揚四海|名揚天下|威震天下|天下無雙|"
    r"一代宗師|登峰造極|出神入化|爐火純青|武林高手|江湖豪傑|俠名遠播"
)
_NAMEPLATE_SUFFIX_RE = re.compile(rf"(?:{_NAMEPLATE_TITLE_PATTERN})$")
_NAMEPLATE_PREFIX_RE = re.compile(rf"^(?:{_NAMEPLATE_TITLE_PATTERN})")
_NAMEPLATE_INLINE_RE = re.compile(rf"(?:{_NAMEPLATE_TITLE_PATTERN})")
_QUESTION_CUE_PREFIX_RE = re.compile(
    r"(以下|下列|請問|試問|問|哪一|哪個|哪種|何者|何種|什麼|甚麼|為何|為什麼|是否|是不是|"
    r"哪|何|誰|幾|多少|何時|何地|哪裡|哪裏)"
)

def _strip_nameplate_suffix(text):
    text = (text or "").strip()
    rough = re.sub(r"[^0-9A-Za-z+\-*/=><\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    if len(rough) < 8:
        return text
    return _NAMEPLATE_SUFFIX_RE.sub("", text).strip()

def _strip_nameplate_prefix(text):
    text = (text or "").strip()
    text = _NAMEPLATE_PREFIX_RE.sub("", text).strip()
    cue = _QUESTION_CUE_PREFIX_RE.search(text)
    if cue and 0 < cue.start() <= 12:
        return text[cue.start():].strip()
    return text

def _strip_nameplate_inline(text):
    text = (text or "").strip()
    rough = re.sub(r"[^0-9A-Za-z+\-*/=><\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    if len(rough) < 8:
        return text
    return _NAMEPLATE_INLINE_RE.sub("", text).strip()

def _rough_questionish_score(text):
    text = (text or "").strip()
    rough = re.sub(r"[^0-9A-Za-z+\-*/=><\u4e00-\u9fff\u3400-\u4dbf？?]+", "", text)
    if not rough:
        return 0
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", rough))
    score = min(35, len(rough)) + cjk_count
    if _QUESTION_CUE_PREFIX_RE.search(text):
        score += 12
    if "？" in text or "?" in text:
        score += 8
    if re.search(r"\d\s*[+\-*/=><]\s*\d|\d{2,}", rough):
        score += 8
    if _NAMEPLATE_SUFFIX_RE.search(text):
        score -= 10
    if _NAMEPLATE_PREFIX_RE.search(text):
        score -= 6
    return score

def strip_countdown_text(text):
    text = _clean_ocr_text(text or "")
    text = re.sub(
        r"\s*(?:剩|剰|賸)\s*[餘余]?\s*(?:時|时)\s*[間问問閒]?"
        r"\s*[:：·・。.,，、\-—是]?\s*\d{1,3}\s*(?:秒)?\s*$",
        "",
        text,
    ).strip()
    countdown = re.search(
        r"剩\s*[餘余]\s*時\s*間\s*[\s:：·・。.,，、\-—是]*(?:\d{1,3}\s*秒?)?"
        r"|(?:剩\s*[餘余]?\s*(?:時\s*間)?|倒\s*數)\s*[\s:：·・。.,，、\-—是]*\d{1,3}\s*秒?",
        text,
    )
    if countdown:
        before = _strip_nameplate_suffix(text[:countdown.start()])
        after = _strip_nameplate_prefix(text[countdown.end():])
        if before and after:
            before_score = _rough_questionish_score(before)
            after_score = _rough_questionish_score(after)
            if before_score >= 12 and after_score >= 12:
                return before + after
            return before if before_score >= after_score else after
        return before or after
    text = re.sub(r"剩\s*[餘余]\s*時\s*間\s*[\s:：·・。.,，、\-—是]*(?:\d{1,3}\s*秒?)?", "", text)
    text = re.sub(r"剩\s*[餘余]?\s*(?:時\s*間)?\s*[\s:：·・。.,，、\-—是]*\d{1,3}\s*秒?", "", text)
    text = re.sub(r"倒\s*數\s*[:：]?\s*\d{1,3}\s*秒?", "", text)
    text = re.sub(r"(?:剩|餘|余|時|間){1,4}\s*[:：]?\s*\d{1,3}\s*秒?", "", text)
    text = re.sub(r"(?<![+\-*/×÷=＝])\b\d{1,3}\s*秒\b(?![+\-*/×÷=＝])", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def normalize_math_symbols(text):
    return (text or "").translate(str.maketrans({
        "＋": "+", "﹢": "+", "－": "-", "﹣": "-",
        "×": "*", "＊": "*", "╳": "*",
        "÷": "/", "／": "/", "＝": "=",
    }))

def fix_numeric_ocr_confusions(text):
    text = normalize_math_symbols(text or "")
    confusable = {
        "O": "0", "o": "0", "Ｏ": "0",
        "I": "1", "l": "1", "Ｉ": "1",
        "S": "5", "s": "5", "Ｓ": "5",
        "Z": "2", "z": "2", "Ｚ": "2",
        "B": "8", "Ｂ": "8",
        "E": "0", "e": "0", "Ｅ": "0",
    }
    math_chars = set("0123456789+-*/=><")
    token_re = re.compile(r"[0-9A-Za-zＯＩＳＺＢＥｏｌｓｚｅ+\-*/=><]+")

    def repl(m):
        seg = m.group(0)
        digit_count = len(re.findall(r"\d", seg))
        has_operator = any(ch in "+-*/=><" for ch in seg)
        if digit_count == 0 or (digit_count < 2 and not has_operator):
            return seg

        chars = list(seg)
        for i, ch in enumerate(chars):
            if ch not in confusable:
                continue
            prev_ch = chars[i - 1] if i > 0 else ""
            next_ch = chars[i + 1] if i + 1 < len(chars) else ""
            if prev_ch in math_chars or next_ch in math_chars:
                chars[i] = confusable[ch]
        return "".join(chars)

    return token_re.sub(repl, text)

_OPT_MARKER_RE = re.compile(
    r'^[\s,，.\(（;；]*(?:'
    r'([1-4１-４]|[Ⅰ-Ⅳ]|[①-④])\s*(?:[\.、:：)）]|\s+)'
    r'|(IV|[IiLl]{1,3})\s*[\.、:：)）]'
    r'|1([1-4１-４])\s*[\.、:：)）]'
    r')\s*'
)
_OPT_INLINE_RE = re.compile(
    r'[\(（;；]?\s*(?:'
    r'([1-4１-４]|[Ⅰ-Ⅳ]|[①-④])\s*(?:[\.、:：)）]|\s+)'
    r'|(IV|[IiLl]{1,3})\s*[\.、:：)）]'
    r'|1([1-4１-４])\s*[\.、:：)）]'
    r')\s*'
)

def _option_marker_num(text):
    m = _OPT_MARKER_RE.match((text or "").strip())
    if not m:
        return None
    raw = m.group(1) or m.group(2) or m.group(3)
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
    text = strip_countdown_text(text or "")
    if re.match(r"^\s*[\(（;；]?\s*[1-4１-４]\s*[\.．](?=\d)", text):
        return text.strip()
    return _OPT_MARKER_RE.sub("", text, count=1).strip()

def _strip_after_first_option_marker(text):
    text = strip_countdown_text(text or "")
    m = _OPT_INLINE_RE.search(text)
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

def match_map_keyword(clean_text, clean_keywords):
    clean_text = clean_map_name_text(clean_text)
    best_kw = ""
    best_score = 0.0
    for keyword in clean_keywords or []:
        if not keyword:
            continue
        if keyword in clean_text or clean_text in keyword:
            score = min(len(clean_text), len(keyword)) / max(1, max(len(clean_text), len(keyword)))
            score = max(score, 0.98 if keyword == clean_text else score)
        else:
            score = SequenceMatcher(None, clean_text, keyword).ratio()
        if score > best_score:
            best_kw, best_score = keyword, score
    return best_kw, best_score

_QUESTION_CONFUSABLES = str.maketrans({
    "？": "", "?": "", "，": "", ",": "", "。": "", ".": "",
    "：": "", ":": "", "；": "", ";": "", "、": "",
    "（": "", "）": "", "(": "", ")": "", "「": "", "」": "",
    "『": "", "』": "", "【": "", "】": "", "《": "", "》": "",
    "！": "", "!": "", "　": "",
})

def normalize_question_text(text):
    text = strip_countdown_text(text or "")
    text = fix_numeric_ocr_confusions(text)
    text = re.sub(r"[\(（]?\s*[1-4１-４]\s*[\)）\.、:：].*", "", text)
    text = text.translate(_QUESTION_CONFUSABLES)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Za-z+\-*/=><\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    return text.strip()

def _is_question_title_line(text):
    line = re.sub(r"\s+", "", _clean_ocr_text(text or ""))
    if not line:
        return True
    title_patterns = [
        r"(黃|壽|寿)?易.*(大|太)?俠.*四選一",
        r"(大|太)?俠.*活動.*輔助",
        r"四選一題?",
        r"選邊站",
        r"機智擂台",
    ]
    return len(line) <= 18 and any(re.search(pat, line) for pat in title_patterns)

_QUESTION_CUE_RE = re.compile(
    r"(以下|下列|請問|試問|問|哪一|哪個|哪種|何者|何種|什麼|甚麼|為何|為什麼|是否|是不是|"
    r"哪|何|誰|幾|多少|何時|何地|哪裡|哪裏)"
)

def _looks_like_question_prefix_noise(prefix):
    norm = normalize_question_text(prefix)
    if not norm:
        return True
    if len(norm) <= 8:
        return True
    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", norm))
    digit_count = len(re.findall(r"\d", norm))
    return len(norm) <= 14 and digit_count >= 1 and cjk_count <= 8

def clean_question_candidate(text):
    text = strip_countdown_text(text or "")
    text = _strip_nameplate_inline(_strip_nameplate_prefix(_strip_nameplate_suffix(text)))
    text = fix_numeric_ocr_confusions(text)
    text = re.sub(r"^\s*(?:(?:黃|壽|寿)?易.*?(?:大|太)?俠.*?四選一|四選一題?|選邊站|機智擂台)\s*[:：、，。\-—]*\s*", "", text)
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    lines = [line for line in lines if not _is_question_title_line(line)]
    if lines:
        question_lines = [line for line in lines if "？" in line or "?" in line]
        if question_lines:
            text = question_lines[-1]
        else:
            text = max(lines, key=lambda line: len(normalize_question_text(line)))
    text = re.sub(r"^\s*(?:題\s*)?\d{1,2}\s*[\.\.、:：\)）]\s*", "", text)
    cue = _QUESTION_CUE_RE.search(text)
    if cue and 0 < cue.start() <= 18:
        if _looks_like_question_prefix_noise(text[:cue.start()]):
            text = text[cue.start():]
    text = re.sub(r"^\s*(?:題\s*)?\d{1,2}\s*", "", text)
    text = re.sub(r"^[\s:：、，。]+", "", text)
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
    min_len = min(len(a_norm), len(b_norm))
    if min_len >= 8:
        prev = [0] * (len(b_norm) + 1)
        for ca in a_norm:
            cur = [0]
            for j, cb in enumerate(b_norm, start=1):
                cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[-1]))
            prev = cur
        lcs = prev[-1]
        coverage = lcs / max(1, min_len)
        balanced = (2 * lcs) / max(1, len(a_norm) + len(b_norm))
        if coverage >= 0.86:
            norm_score = max(norm_score, balanced, coverage * 0.90)
    return max(raw_score, norm_score)

def _looks_like_nameplate_text(text):
    clean = strip_countdown_text(text or "")
    norm = normalize_question_text(clean)
    if not norm:
        return True
    has_question_cue = bool(_QUESTION_CUE_RE.search(clean) or "？" in clean or "?" in clean)
    has_math = bool(re.search(r"\d\s*[+\-*/=><]\s*\d|\d{2,}", norm))
    if has_question_cue or has_math:
        return False

    lines = [line.strip() for line in re.split(r"[\r\n]+", clean) if line.strip()]
    line_norms = [normalize_question_text(line) for line in lines]
    if len(lines) >= 2 and all(0 < len(n) <= 8 for n in line_norms):
        return True

    cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", norm))
    if len(norm) <= 6:
        return True
    if len(norm) <= 12:
        sentence_markers = r"(是|為|在|有|與|和|或|的|之|指|稱|屬|包含|不是|正確|錯誤)"
        if cjk_count < 5 or not re.search(sentence_markers, clean):
            return True
    return False

def normalize_option_text(text):
    text = fix_numeric_ocr_confusions(_strip_option_marker(_clean_ocr_text(text or "")))
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^0-9A-Za-z+\-*/=><_\u4e00-\u9fff\u3400-\u4dbf]+", "", text)
    return text.strip()

def clean_option_candidate(text, expected_num=None):
    text = strip_countdown_text(text or "")
    text = fix_numeric_ocr_confusions(_clean_ocr_text(text))
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    lines = [line for line in lines if not _is_question_title_line(line)]
    if lines:
        if expected_num:
            marked = [
                line for line in lines
                if _option_marker_num(line) == expected_num
            ]
            text = marked[0] if marked else max(lines, key=lambda line: len(normalize_option_text(line)))
        else:
            text = max(lines, key=lambda line: len(normalize_option_text(line)))
    text = _strip_option_marker(text)
    opt, _ = _split_embedded_question(text)
    opt = re.sub(r"^[\s:：、，。;；]+", "", opt)
    opt = re.sub(r"[\s;；,，？！。]+$", "", opt).strip()
    return opt

def _option_candidate_score(option, question=""):
    clean = clean_option_candidate(option)
    norm = normalize_option_text(clean)
    if not norm:
        return 0.0
    if re.fullmatch(r"\d+(?:\.\d+)?", norm):
        return max(12.0, len(norm) * 3.0)
    score = min(28, len(norm)) * 1.2
    score += len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", norm)) * 1.0
    score += len(re.findall(r"\d", norm)) * 0.5
    score += len(re.findall(r"[+\-*/=><]", norm)) * 1.2
    if len(norm) <= 1:
        score -= 5
    if len(norm) > 32:
        score -= (len(norm) - 32) * 1.0
    if _is_question_title_line(clean):
        score -= 25
    if len(_OPT_MARKER_RE.findall(clean)) >= 2 or len(_OPT_INLINE_RE.findall(clean)) >= 2:
        score -= 18
    if re.search(r"(剩\s*[餘余]?時間|倒\s*數|\d{1,3}\s*秒)", clean):
        score -= 18
    q_norm = normalize_question_text(question)
    if q_norm and len(norm) >= 7:
        sim = SequenceMatcher(None, norm, q_norm).ratio()
        if norm in q_norm or q_norm in norm or sim >= 0.78:
            score -= 45
    return max(0.0, score)

def ocr_option_image(pil_img, expected_num=None, question="", on_detail=None):
    candidates = []
    prepared_images = [
        _prepare_text_region_ocr_image(pil_img, min_value=120),
        _prepare_ocr_image(pil_img),
    ]
    seen = set()
    for idx, prepared in enumerate(prepared_images, start=1):
        sig = (prepared.size, compute_phash(prepared))
        if sig in seen:
            continue
        seen.add(sig)
        raw = ocr_prepared_image(prepared, on_detail=on_detail)
        clean = clean_option_candidate(raw, expected_num=expected_num)
        score = _option_candidate_score(clean, question=question)
        if clean and score >= 4:
            candidates.append((score, len(normalize_option_text(clean)), idx, clean))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][3]

def _ocr_options_by_cells(options_img, question="", on_detail=None):
    if options_img is None:
        return []
    w, h = options_img.size
    if w < 80 or h < 24:
        return []
    cells = {
        1: (0.00, 0.00, 0.35, 0.55),
        2: (0.50, 0.00, 1.00, 0.55),
        3: (0.00, 0.55, 0.35, 1.00),
        4: (0.50, 0.55, 1.00, 1.00),
    }
    options = []
    for num in range(1, 5):
        l, t, r, b = cells[num]
        crop = options_img.crop((
            max(0, int(w * l)),
            max(0, int(h * t)),
            min(w, int(w * r)),
            min(h, int(h * b)),
        ))
        options.append(ocr_option_image(crop, expected_num=num, question=question, on_detail=on_detail))
    if on_detail and quiz_option_count(options) >= 3:
        on_detail("四選一選項已使用分格辨識，提高順序與文字穩定度")
    return options

def _choose_best_quiz_options(question, *option_sets, bonus_options=None):
    best = ["", "", "", ""]
    best_scores = [0.0, 0.0, 0.0, 0.0]
    seen = set()
    bonus_norms = []
    if bonus_options:
        for idx, opt in enumerate((bonus_options or [])[:4]):
            bonus_norms.append(normalize_option_text(clean_option_candidate(opt, expected_num=idx + 1)))
    for options in option_sets:
        for idx, opt in enumerate((options or [])[:4]):
            clean = clean_option_candidate(opt, expected_num=idx + 1)
            norm = normalize_option_text(clean)
            if not clean or not norm:
                continue
            score = _option_candidate_score(clean, question=question)
            if score <= 0:
                continue
            if idx < len(bonus_norms) and bonus_norms[idx] and bonus_norms[idx] == norm:
                score += 3.0
            current_norm = normalize_option_text(best[idx])
            duplicate_elsewhere = norm in seen and norm != current_norm
            if duplicate_elsewhere:
                score -= 8
            if score > best_scores[idx] or (score >= best_scores[idx] * 0.9 and len(norm) > len(current_norm)):
                if current_norm in seen:
                    seen.discard(current_norm)
                best[idx] = clean
                best_scores[idx] = score
                seen.add(norm)
    return _filter_quiz_options(question, best)

def _filter_quiz_options(question, options):
    """Remove OCR spillover where the question line is captured as an option."""
    q_norm = normalize_question_text(question)
    cleaned = []
    seen = set()
    for opt in options[:4]:
        opt_text = _strip_option_marker(_clean_ocr_text(opt))
        opt_text = re.sub(r"[\s;,\uFF1B\uFF0C\uFF1F\uFF01\u3002]+$", "", opt_text).strip()
        opt_norm = normalize_option_text(opt_text)
        if not opt_text or not opt_norm:
            cleaned.append("")
            continue

        is_question_like = False
        if q_norm and len(opt_norm) >= 7:
            sim = SequenceMatcher(None, opt_norm, q_norm).ratio()
            contained = opt_norm in q_norm or q_norm in opt_norm
            is_question_like = contained or sim >= 0.78

        if is_question_like or opt_norm in seen:
            cleaned.append("")
            continue

        seen.add(opt_norm)
        cleaned.append(opt_text)
    return cleaned

def quiz_option_count(options):
    seen = set()
    count = 0
    for opt in options[:4]:
        opt_norm = normalize_option_text(opt)
        if opt_norm and opt_norm not in seen:
            seen.add(opt_norm)
            count += 1
    return count

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

def _ocr_parse_quiz_by_layout(full_img, question_img=None, options_img=None, on_detail=None):
    q_text = ""
    if question_img is not None:
        q_data = ocr_image_details(question_img, on_detail=on_detail)
        q_text = clean_question_candidate(q_data.get("text", ""))
        if q_text and _question_candidate_score(q_text) < 12:
            q_text = ""
        if not q_text:
            q_text = ocr_question_image(question_img, on_detail=on_detail)
        q_option_rows = []
        for line in q_data.get("lines", []):
            q_option_rows.extend(_option_rows_from_ocr_line(line))
        if len(q_option_rows) >= 2:
            q_text = _strip_after_first_option_marker(q_text)

    option_source = options_img or full_img
    data = ocr_image_details(option_source, on_detail=on_detail)
    lines = data.get("lines", [])
    if not data.get("text") and not lines:
        return q_text, []

    option_rows = []
    for line in lines:
        option_rows.extend(_option_rows_from_ocr_line(line))

    if not option_rows:
        return q_text, []

    slots = {}
    for row in sorted(option_rows, key=lambda r: (r["num"], r["top"], r["left"])):
        opt_text, embedded_q = _split_embedded_question(row["text"])
        if embedded_q and not q_text:
            q_text = embedded_q
        if opt_text:
            slots.setdefault(row["num"], opt_text)
    options = _filter_quiz_options(q_text, [slots.get(k, "") for k in range(1, 5)])
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
        q_text = clean_question_candidate("".join(q_lines))

    return clean_question_candidate(q_text), options[:4]

def ocr_parse_quiz(full_img, question_img=None, options_img=None, on_detail=None):
    """OCR 彈窗圖，分離題目和選項。
    question_img：若提供，獨立辨識題目（避免 2 欄選項佈局干擾讀取順序）。
    回傳 (question_str, [opt1, opt2, opt3, opt4])。"""
    strict_question_region = question_img is not None
    high_precision_quiz4 = options_img is not None
    if _OCR_ENGINE == "windows":
        q_by_layout, opts_by_layout = _ocr_parse_quiz_by_layout(
            full_img, question_img=question_img, options_img=options_img, on_detail=on_detail)
    else:
        q_by_layout, opts_by_layout = "", []
    if (
        not high_precision_quiz4
        and _OCR_ENGINE == "windows"
        and q_by_layout
        and len([o for o in opts_by_layout if o.strip()]) >= 2
    ):
        return q_by_layout, opts_by_layout

    cjk = r'一-鿿㐀-䶿'
    def _norm(t):
        t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[{cjk}])', '', t)
        t = re.sub(rf'(?<=[{cjk}])[ \t]+(?=[，。！？；：、,.])', '', t)
        t = re.sub(rf'(?<=[，。！？；：、,.])[ \t]+(?=[{cjk}])', '', t)
        return t

    _OPT = re.compile(
        r'[\(（;；]?\s*'
        r'(?:[1-4１-４]|[Ⅰ-Ⅳ]|[①-④]|IV|[IiLl]{1,3})'
        r'\s*[\.、:：)）]'
    )

    def _question_from_text(raw):
        cand = _norm((raw or "").strip())
        cand = strip_countdown_text(cand)
        if not cand:
            return ""
        marker = _OPT.search(cand)
        if marker:
            cand = cand[:marker.start()].strip()
        qm = max(cand.rfind('？'), cand.rfind('?'))
        if qm >= 0:
            start = max(cand.rfind('\n', 0, qm), cand.rfind('\r', 0, qm)) + 1
            cand = cand[start:qm+1].strip()
        return clean_question_candidate(cand)

    # 獨立辨識題目（用題目區域裁切圖，避免 2 欄選項讀取順序干擾）
    q_text = q_by_layout
    if question_img is not None and _question_candidate_score(q_text) < 45:
        cand = ocr_question_image(question_img, on_detail=on_detail, high_precision=high_precision_quiz4)
        # 若含 2 個以上選項標記，代表框選範圍涵蓋到選項區，放棄此結果
        if cand and len(_OPT.findall(cand)) < 2 and _question_candidate_score(cand) >= _question_candidate_score(q_text):
            q_text = cand

    if not q_text and not strict_question_region:
        raw_full = ocr_image(full_img, on_detail=on_detail)
        q_text = _question_from_text(raw_full)

    option_source = options_img or full_img
    cell_options = _ocr_options_by_cells(option_source, q_text, on_detail=on_detail) if high_precision_quiz4 else []
    text = ocr_image(option_source, on_detail=on_detail)
    if not text:
        return q_text, _choose_best_quiz_options(q_text, opts_by_layout, cell_options)

    text = _norm(text)
    text = strip_countdown_text(text)

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

        options = _filter_quiz_options(q_text, [slots.get(k, '') for k in range(1, 5)])
        while options and not options[-1]:
            options.pop()

        if not q_text:
            before = text[:markers[0].start()].strip()
            if len(before) > 4:
                q_text = clean_question_candidate(before)
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
                        q_text = clean_question_candidate(q_cand)

        q_text = clean_question_candidate(q_text)
        bonus_options = options if quiz_option_count(options) == 4 else None
        return q_text, _choose_best_quiz_options(
            q_text, opts_by_layout, options, cell_options, bonus_options=bonus_options
        )[:4]

    # fallback：找第一個後面跟著另一個標記的位置切分
    m = None
    for candidate in _OPT.finditer(text):
        if _OPT.search(text[candidate.end():candidate.end()+150]):
            m = candidate
            break
    if not m:
        fallback_q = q_text if strict_question_region else (q_text or text.strip())
        fallback_q = clean_question_candidate(fallback_q)
        if _question_candidate_score(fallback_q) < 12:
            fallback_q = ""
        return fallback_q, _choose_best_quiz_options(fallback_q, opts_by_layout, cell_options)
    if not q_text:
        q_text = text[:m.start()].strip()
    parts = _OPT.split(text[m.start():])
    options = [re.sub(r'[\s;；,，]+$', '', p).strip() for p in parts if p.strip()][:4]
    q_text = clean_question_candidate(q_text)
    return q_text, _choose_best_quiz_options(q_text, opts_by_layout, options, cell_options)

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

def _safe_filename_part(text, max_len=36):
    text = normalize_question_text(text or "") or "unknown"
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\u3400-\u4dbf]+", "_", text)
    text = text.strip("_") or "unknown"
    return text[:max_len]

def _attach_capture(entry, capture_path):
    if not capture_path:
        return
    entry["capture_path"] = capture_path
    captures = entry.get("captures")
    if not isinstance(captures, list):
        captures = []
    if capture_path not in captures:
        captures.append(capture_path)
    entry["captures"] = captures[-8:]

def _is_ocr_failed_placeholder(question):
    text = str(question or "")
    return text.startswith("[OCR失敗]") or text.startswith("[待校正]")

_CAPTURE_REGION_CACHE = {}

def _capture_region_path(capture_path, region="question"):
    if not capture_path:
        return ""
    if region == "question" and capture_path.endswith("_popup.png"):
        return capture_path[:-10] + "_question.png"
    if region == "options" and capture_path.endswith("_popup.png"):
        return capture_path[:-10] + "_options.png"
    return ""

def _load_capture_region(capture_path, region="question"):
    path = _capture_region_path(capture_path, region)
    if not path or not os.path.exists(path):
        return None
    key = (path, region)
    cached = _CAPTURE_REGION_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    _CAPTURE_REGION_CACHE[key] = img
    if len(_CAPTURE_REGION_CACHE) > 96:
        _CAPTURE_REGION_CACHE.pop(next(iter(_CAPTURE_REGION_CACHE)))
    return img

def _entry_capture_paths(entry):
    paths = []
    captures = entry.get("captures")
    if isinstance(captures, list):
        paths.extend(captures)
    if entry.get("capture_path"):
        paths.append(entry.get("capture_path"))
    deduped = []
    seen = set()
    for path in paths:
        if path and path not in seen:
            seen.add(path)
            deduped.append(path)
    return deduped[-8:]

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
            for e in self.confirmed_entries():
                if e.get("phash") and phash_distance(phash, e["phash"]) < 5:
                    return e
        if question:
            best = self.find_similar(question, threshold=threshold)
            if best:
                return best[0]
        return None

    def find_similar(self, question, threshold=0.80):
        best, best_score = None, 0.0
        for e in self.confirmed_entries():
            s = question_similarity(question, e.get("question", ""))
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return best, round(best_score, 3)
        return None

    def find_by_question_image(self, question_img, threshold=0.88):
        best, best_score = None, 0.0
        for e in self.confirmed_entries():
            for capture_path in _entry_capture_paths(e):
                ref = _load_capture_region(capture_path, "question")
                if ref is None:
                    continue
                s = text_mask_similarity(question_img, ref, size=(220, 64))
                if s > best_score:
                    best_score = s
                    best = e
        if best and best_score >= threshold:
            return dict(best, image_similarity=round(best_score, 3))
        return None

    def is_confirmed(self, entry):
        return bool(entry.get("answer_idx")) and quiz_option_count(entry.get("options", [])) >= 4

    def confirmed_entries(self):
        return [e for e in self.entries if self.is_confirmed(e)]

    def pending_entries(self):
        return [e for e in self.entries if not self.is_confirmed(e)]

    def pending_indices(self):
        return [i for i, e in enumerate(self.entries) if not self.is_confirmed(e)]

    def confirmed_indices(self):
        return [i for i, e in enumerate(self.entries) if self.is_confirmed(e)]

    def find_pending_similar(self, question, threshold=0.68):
        best, best_score = None, 0.0
        for e in self.pending_entries():
            s = question_similarity(question, e.get("question", ""))
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return best, round(best_score, 3)
        return None

    def merge_pending(self, phash, question, options, threshold=0.68, capture_path=None):
        if _is_ocr_failed_placeholder(question):
            return False
        found = self.find_pending_similar(question, threshold=threshold)
        if not found:
            return False
        entry, score = found
        old_count = quiz_option_count(entry.get("options", []))
        new_count = quiz_option_count(options)
        if phash:
            entry["phash"] = phash
        question_updated = len(normalize_question_text(question)) > len(normalize_question_text(entry.get("question", "")))
        options_updated = new_count > old_count
        if question_updated:
            entry["question"] = question
        if options_updated:
            entry["options"] = options
        entry["source"] = f"待校正合併 {score:.0%}"
        if question_updated or options_updated or not _entry_capture_paths(entry):
            _attach_capture(entry, capture_path)
        self._save()
        return True

    def upsert(self, phash, question, answer_idx, answer_text, options, capture_path=None):
        for e in self.entries:
            merge_threshold = 0.92 if self.is_confirmed(e) else 0.68
            if e.get("question") == question or question_similarity(question, e.get("question", "")) >= merge_threshold:
                e.update(phash=phash, question=question, answer_idx=answer_idx,
                         answer_text=answer_text, options=options, source="手動")
                _attach_capture(e, capture_path)
                self._save(); return
        entry = dict(phash=phash, question=question,
                     answer_idx=answer_idx, answer_text=answer_text,
                     options=options, source="手動")
        _attach_capture(entry, capture_path)
        self.entries.append(entry)
        self._save()

    def add_pending(self, phash, question, options, threshold=0.68, capture_path=None):
        if self.merge_pending(phash, question, options, threshold=threshold, capture_path=capture_path):
            return "merged"
        found = None if _is_ocr_failed_placeholder(question) else self.find_similar(question, threshold=threshold)
        if found and self.is_confirmed(found[0]):
            return "answered"
        entry = dict(phash=phash, question=question,
                     answer_idx=None, answer_text="",
                     options=options, source="待校正")
        _attach_capture(entry, capture_path)
        self.entries.append(entry)
        self._save()
        return "added"

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
        for e in self.confirmed_entries():
            s = question_similarity(question, e["question"])
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return dict(best, similarity=round(best_score, 3))
        return None

    def find_by_question_image(self, question_img, threshold=0.88):
        best, best_score = None, 0.0
        for e in self.confirmed_entries():
            for capture_path in _entry_capture_paths(e):
                ref = _load_capture_region(capture_path, "question")
                if ref is None:
                    continue
                s = image_similarity(question_img, ref, size=(220, 64))
                if s > best_score:
                    best_score = s
                    best = e
        if best and best_score >= threshold:
            return dict(best, image_similarity=round(best_score, 3))
        return None

    def confirmed_entries(self):
        return [e for e in self.entries if e.get("answer") in ("O", "X")]

    def pending_entries(self):
        return [e for e in self.entries if e.get("answer") not in ("O", "X")]

    def confirmed_indices(self):
        return [i for i, e in enumerate(self.entries) if e.get("answer") in ("O", "X")]

    def pending_indices(self):
        return [i for i, e in enumerate(self.entries) if e.get("answer") not in ("O", "X")]

    def find_pending_similar(self, question, threshold=0.68):
        best, best_score = None, 0.0
        for e in self.pending_entries():
            s = question_similarity(question, e.get("question", ""))
            if s > best_score:
                best_score = s; best = e
        if best and best_score >= threshold:
            return best, round(best_score, 3)
        return None

    def add(self, question, answer):
        existing = self.lookup(question, threshold=0.68 if answer is None else 0.80)
        if existing:
            return False
        self.entries.append({"question": question, "answer": answer})
        self._save()
        return True

    def upsert(self, question, answer, old_question=None, capture_path=None):
        for e in self.entries:
            same_old = old_question and e.get("question") == old_question
            same_new = e.get("question") == question
            similar = question_similarity(question, e.get("question", "")) >= 0.80
            if same_old or same_new or similar:
                e["question"] = question
                e["answer"] = answer
                _attach_capture(e, capture_path)
                self._save()
                return
        entry = {"question": question, "answer": answer}
        _attach_capture(entry, capture_path)
        self.entries.append(entry)
        self._save()

    def add_pending(self, question, threshold=0.68, capture_path=None):
        if not _is_ocr_failed_placeholder(question) and self.lookup(question, threshold=threshold):
            return "answered"
        existing = None if _is_ocr_failed_placeholder(question) else self.find_pending_similar(question, threshold=threshold)
        if existing:
            _attach_capture(existing, capture_path)
            self._save()
            return "merged"
        entry = {"question": question, "answer": None}
        _attach_capture(entry, capture_path)
        self.entries.append(entry)
        self._save()
        return "added"

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
        self._last_sig_bits = None
        self._ignored_sig_bits = None
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
        self._map_miss_count  = 0
        self._idle_map_check_time = 0.0
        self._last_coord_region = None
        self._last_auto_learn_digits = set()
        self._last_capture_key = None
        self._force_next_recognition = False

    def set_mode(self, mode):
        self.mode             = mode
        self._popup_on        = False
        self._last_ph         = None
        self._last_sig_bits   = None
        self._ignored_sig_bits = None
        self._last_recognition_time = 0.0
        self._last_api_ph     = None
        self._last_api_time   = 0.0
        self._popup_api_used = False
        self._gemini_block_until = 0.0
        self._map_ok          = True
        self._map_check_time  = 0.0
        self._last_map_text   = ""
        self._map_confirmed_at = 0.0
        self._map_miss_count  = 0
        self._idle_map_check_time = 0.0
        self._last_capture_key = None
        self._force_next_recognition = False

    def force_next_recognition(self):
        self._force_next_recognition = True
        self._last_recognition_time = 0.0
        self._last_sig_bits = None
        self._ignored_sig_bits = None
        self._last_ph = None

    def ignore_current_popup(self):
        self._ignored_sig_bits = self._last_sig_bits
        self._last_recognition_time = time.time()

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
        return self._crop_region(img, w, h, r)

    def _crop_region(self, img, w, h, r):
        x1 = int(r.get("left",  0) * w); y1 = int(r.get("top",    0) * h)
        x2 = int(r.get("right", 1) * w); y2 = int(r.get("bottom", 1) * h)
        return img.crop((x1, y1, x2, y2))

    def _map_name_fallback_regions(self):
        return [
            {"left": 0.66, "top": 0.000, "right": 0.87, "bottom": 0.055},
            {"left": 0.64, "top": 0.000, "right": 0.89, "bottom": 0.060},
        ]

    def _popup_region_key(self):
        return "sidestand_popup_full_region" if self.mode == "sidestand" else "popup_full_region"

    def _question_region_key(self):
        return "sidestand_question_region" if self.mode == "sidestand" else "question_region"

    def _quiz_signature_image(self, q_img, opt_img):
        qw, qh = q_img.size
        ow, oh = opt_img.size
        sw = max(1, qw, ow)
        sh = max(1, qh + oh)
        sig = Image.new("RGB", (sw, sh), (0, 0, 0))
        sig.paste(q_img.convert("RGB"), (0, 0))
        sig.paste(opt_img.convert("RGB"), (0, qh))
        return sig

    def sample_brightness(self, img, w, h):
        cx = int(self.config.get("popup_check_x", 0.45) * w)
        cy = int(self.config.get("popup_check_y", 0.10) * h)
        r  = 6
        region = img.crop((max(0,cx-r), max(0,cy-r), min(w,cx+r), min(h,cy+r)))
        pixels = list(region.getdata())
        if not pixels: return 255
        return sum(sum(p) for p in pixels) / (len(pixels) * 3)

    def popup_edge_strength(self, img, w, h):
        crop = self._crop(img, w, h, self._popup_region_key()).convert("L")
        cw, ch = crop.size
        if cw <= 0 or ch < 4:
            return 0.0
        sample_w = max(16, min(cw, cw // 3))
        sample_h = max(8, min(ch, ch // 3))
        if sample_w != cw or sample_h != ch:
            crop = crop.resize((sample_w, sample_h), Image.Resampling.BILINEAR)
            cw, ch = crop.size
        pixels = list(crop.getdata())
        row_means = []
        for y in range(ch):
            start = y * cw
            row_means.append(sum(pixels[start:start + cw]) / max(1, cw))
        edges = [abs(row_means[i] - row_means[i - 1]) for i in range(1, len(row_means))]
        if not edges:
            return 0.0
        top = sorted(edges, reverse=True)[:10]
        return sum(top) / len(top)

    def _popup_frame_parts(self, img, w, h):
        crop = self._crop(img, w, h, self._popup_region_key()).convert("RGB")
        if crop.width > 420:
            ratio = 420 / crop.width
            crop = crop.resize((420, max(1, int(crop.height * ratio))), Image.Resampling.BILINEAR)
        cw, ch = crop.size
        if cw <= 8 or ch <= 8:
            return {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}
        pixels = crop.load()

        def is_frame_pixel(x, y):
            r, g, b = pixels[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            return mx >= 120 and mx - mn <= 120

        row_scores = []
        for y in range(ch):
            row_scores.append(sum(1 for x in range(cw) if is_frame_pixel(x, y)) / cw)
        col_scores = []
        for x in range(cw):
            col_scores.append(sum(1 for y in range(ch) if is_frame_pixel(x, y)) / ch)

        top = max(row_scores[:max(4, ch // 8)])
        bottom = max(row_scores[int(ch * 0.72):])
        left = max(col_scores[:max(4, cw // 10)])
        right = max(col_scores[int(cw * 0.90):])
        return {"top": top, "bottom": bottom, "left": left, "right": right}

    def popup_frame_signal(self, img, w, h):
        parts = self._popup_frame_parts(img, w, h)
        top = parts["top"]
        bottom = parts["bottom"]
        left = parts["left"]
        return (top + bottom + left) / 3.0

    def popup_bottom_frame_signal(self, img, w, h):
        return self._popup_frame_parts(img, w, h)["bottom"]

    def popup_text_signal(self, img, w, h):
        crop = self._crop(img, w, h, self._question_region_key())
        if crop.width <= 0 or crop.height <= 0:
            return 0.0
        mask = _bright_text_mask(crop, min_value=145, max_delta=120)
        data = list(mask.getdata())
        if not data:
            return 0.0
        text_pixels = sum(1 for p in data if p > 0)
        rows_with_text = 0
        for y in range(mask.height):
            row = data[y * mask.width:(y + 1) * mask.width]
            if sum(1 for p in row if p > 0) >= 2:
                rows_with_text += 1
        if rows_with_text < 3:
            return 0.0
        density = text_pixels / max(1, mask.width * mask.height)
        if density > 0.18:
            return 0.0
        return density

    def quiz4_option_panel_signal(self, options_img):
        """Estimate whether the options crop is inside the dark quiz dialog panel."""
        if options_img is None or options_img.width < 40 or options_img.height < 18:
            return 0.0
        crop = options_img.convert("RGB")
        x_pad = max(1, int(crop.width * 0.015))
        y_pad = max(1, int(crop.height * 0.08))
        if crop.width > x_pad * 2 and crop.height > y_pad * 2:
            crop = crop.crop((x_pad, y_pad, crop.width - x_pad, crop.height - y_pad))
        scale = min(1.0, 260 / max(1, crop.width))
        if scale < 1.0:
            crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))), Image.Resampling.BILINEAR)
        pixels = list(crop.getdata())
        if not pixels:
            return 0.0
        dark_panel = 0
        colorful = 0
        for r, g, b in pixels:
            mx, mn = max(r, g, b), min(r, g, b)
            if mx <= 96 and mx - mn <= 58:
                dark_panel += 1
            if mx >= 125 and mx - mn >= 85:
                colorful += 1
        dark_ratio = dark_panel / len(pixels)
        colorful_ratio = colorful / len(pixels)
        if colorful_ratio > 0.10:
            dark_ratio *= max(0.0, 1.0 - (colorful_ratio - 0.10) * 3.0)
        return dark_ratio

    def is_popup_visible(self, img, w, h):
        frame_key = "sidestand_popup_frame_threshold" if self.mode == "sidestand" else "quiz4_popup_frame_threshold"
        frame_signal = self.popup_frame_signal(img, w, h)
        if frame_signal < float(self.config.get(frame_key, 0.35)):
            return False
        if self.mode != "sidestand":
            bottom_signal = self.popup_bottom_frame_signal(img, w, h)
            if bottom_signal < float(self.config.get("quiz4_popup_bottom_frame_threshold", 0.35)):
                return False
        brightness = self.sample_brightness(img, w, h)
        threshold = float(self.config.get("popup_brightness_threshold", 80))
        if brightness >= threshold:
            return False
        edge = self.popup_edge_strength(img, w, h)
        edge_threshold = float(self.config.get("popup_edge_threshold", 35))
        if edge_threshold <= 0 or edge >= edge_threshold:
            return True
        margin = float(self.config.get("popup_brightness_margin", 18))
        return brightness <= threshold - margin

    def is_cropped_popup_visible(self, crop_img):
        cfg = dict(self.config)
        cfg["popup_full_region"] = {"left": 0, "top": 0, "right": 1, "bottom": 1}
        cfg["sidestand_popup_full_region"] = {"left": 0, "top": 0, "right": 1, "bottom": 1}
        cfg["question_region"] = {"left": 0, "top": 0, "right": 1, "bottom": 0.58}
        cfg["sidestand_question_region"] = {"left": 0, "top": 0, "right": 1, "bottom": 0.58}
        cfg["options_region"] = {"left": 0, "top": 0.58, "right": 1, "bottom": 1}
        probe = GameDetector(cfg, None, None)
        probe.mode = self.mode
        w, h = crop_img.width, crop_img.height
        frame_signal = probe.popup_frame_signal(crop_img, w, h)
        frame_key = "sidestand_popup_frame_threshold" if self.mode == "sidestand" else "quiz4_popup_frame_threshold"
        frame_threshold = max(0.28, float(self.config.get(frame_key, 0.35)) - 0.08)
        if frame_signal < frame_threshold:
            return False
        return True

    def _map_grace_seconds(self):
        if bool(float(self.config.get("map_strict_mode", 1))):
            return 0.0
        return max(0.0, float(self.config.get("map_leave_grace_seconds", 5)))

    def _check_map_name(self, img, w, h, force=False):
        """定期 OCR 右上地圖名稱，有關鍵字才允許進入辨識流程。"""
        keywords = self.config.get("quiz_map_keywords", [])
        if not keywords:
            self._map_miss_count = 0
            return True  # 未設定關鍵字 → 不篩選
        now = time.time()
        if not force and now - self._map_check_time < self.config.get("map_check_interval", 3):
            return self._map_ok  # 使用快取
        self._map_check_time = now
        map_img = self._crop(img, w, h, "map_name_region")
        clean_keywords = normalize_map_keywords(keywords)
        clean_text = ocr_map_name_image(map_img, on_detail=self._on_detail)
        text_keyword, text_score = match_map_keyword(clean_text, clean_keywords)
        text_matched = bool(text_keyword) and text_score >= 0.80
        if not text_matched:
            for region in self._map_name_fallback_regions():
                alt_img = self._crop_region(img, w, h, region)
                alt_text = ocr_map_name_image(alt_img, on_detail=self._on_detail)
                alt_keyword, alt_score = match_map_keyword(alt_text, clean_keywords)
                if alt_score > text_score:
                    clean_text = alt_text
                    text_keyword = alt_keyword
                    text_score = alt_score
                    map_img = alt_img
                if alt_keyword and alt_score >= 0.80:
                    text_matched = True
                    break
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
            image_matched = best_similarity >= threshold
            matched = text_matched or image_matched
            grace = self._map_grace_seconds()
            in_grace = self._map_confirmed_at > 0 and (now - self._map_confirmed_at) < grace
            if matched:
                self._map_confirmed_at = now
                self._map_miss_count = 0
            elif not in_grace:
                self._map_miss_count += 1
            status_text = f"文字:{text_keyword or clean_text or '空'} {text_score:.0%} 圖片:{best_keyword or '未知'} {best_similarity:.0%}"
            if status_text != self._last_map_text:
                self._last_map_text = status_text
                if text_matched:
                    self._on_detail(f"地圖文字：{clean_text}（命中 {text_keyword}，啟動辨識；圖片 {best_similarity:.0%} 只當參考）")
                elif image_matched:
                    self._on_detail(f"地圖圖片：{best_keyword}（相似度 {best_similarity:.0%}，啟動辨識）")
                elif in_grace:
                    self._on_detail(f"地圖：文字 {text_score:.0%} / 圖片 {best_similarity:.0%}（保護期，維持辨識）")
                else:
                    self._on_detail(f"地圖：文字 {text_score:.0%} / 圖片 {best_similarity:.0%}（未命中，略過）")
            self._map_ok = matched or in_grace
            return self._map_ok

        if not clean_text:
            grace = self._map_grace_seconds()
            in_grace = self._map_confirmed_at > 0 and (now - self._map_confirmed_at) < grace
            if not in_grace:
                self._map_ok = False
                self._map_miss_count += 1
            return self._map_ok
        matched = text_matched
        grace = self._map_grace_seconds()
        in_grace = self._map_confirmed_at > 0 and (now - self._map_confirmed_at) < grace
        if matched:
            self._map_confirmed_at = now
            self._map_miss_count = 0
        elif not in_grace:
            self._map_miss_count += 1
        if clean_text != self._last_map_text:
            self._last_map_text = clean_text
            if matched:
                self._on_detail(f"地圖文字：{clean_text[:30]}（命中 {text_keyword or '關鍵字'}，啟動辨識）")
            elif in_grace:
                self._on_detail(f"地圖文字：{clean_text[:30]}（保護期，維持辨識）")
            else:
                self._on_detail(f"地圖文字：{clean_text[:30]}（未命中關鍵字，略過）")
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
        tmpl_coord, tmpl_raw = read_coord_by_templates(
            coord_img,
            threshold=float(self.config.get("coord_template_threshold", 0.34)),
        )

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
        if tmpl_coord:
            return tmpl_coord, tmpl_raw
        return None, text or tmpl_raw

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

    def _save_pending_capture(self, mode, ph, full_img, q_img, opt_img=None,
                              question="", options=None, reason="pending"):
        if not self.config.get("save_pending_captures", 1):
            return ""
        options = options or []
        key = (
            mode,
            reason,
            ph,
            normalize_question_text(question),
            tuple(normalize_option_text(o) for o in options[:4]),
        )
        if key == self._last_capture_key:
            return ""
        self._last_capture_key = key
        try:
            now = datetime.datetime.now()
            day_dir = os.path.join(CAPTURE_DIR, now.strftime("%Y%m%d"))
            os.makedirs(day_dir, exist_ok=True)
            text_part = _safe_filename_part(question or reason)
            short_hash = hashlib.sha1(
                json.dumps(key, ensure_ascii=False, default=str).encode("utf-8", errors="ignore")
            ).hexdigest()[:8]
            base = f"{now.strftime('%H%M%S')}_{mode}_{reason}_{short_hash}_{text_part}"
            popup_path = os.path.join(day_dir, base + "_popup.png")
            full_img.convert("RGB").save(popup_path)

            region_paths = {}
            if self.config.get("save_capture_regions", 1):
                q_path = os.path.join(day_dir, base + "_question.png")
                q_img.convert("RGB").save(q_path)
                region_paths["question"] = q_path
                if opt_img is not None:
                    o_path = os.path.join(day_dir, base + "_options.png")
                    opt_img.convert("RGB").save(o_path)
                    region_paths["options"] = o_path

            meta = {
                "mode": mode,
                "reason": reason,
                "created_at": now.isoformat(timespec="seconds"),
                "question": question,
                "options": options[:4],
                "phash": ph,
                "popup_path": popup_path,
                "regions": region_paths,
            }
            meta_path = os.path.join(day_dir, base + "_meta.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
                f.write("\n")
            self._on_detail(f"已保存待校正截圖：{os.path.basename(popup_path)}")
            return popup_path
        except Exception as e:
            self._on_detail(f"保存待校正截圖失敗：{type(e).__name__}: {e}")
            return ""

    def _reset_popup_state(self):
        self._popup_on      = False
        self._last_ph       = None
        self._last_sig_bits = None
        self._ignored_sig_bits = None
        self._last_recognition_time = 0.0
        self._last_api_ph   = None
        self._last_api_time = 0.0
        self._popup_api_used = False

    def _handle_map_block(self, on_status):
        keywords = self.config.get("quiz_map_keywords", [])
        auto_stop = bool(float(self.config.get("auto_stop_on_map_leave", 1)))
        stop_misses = max(1, int(float(self.config.get("map_leave_stop_misses", 2))))
        if keywords and auto_stop and self._map_miss_count >= stop_misses:
            on_status("已離開活動場景，停止監測")
            self.stop()
        else:
            on_status("非活動場景，等待中…")

    def _maybe_idle_map_check(self, img, w, h, on_status):
        if not self.config.get("quiz_map_keywords", []):
            return
        now = time.time()
        interval = max(
            float(self.config.get("map_check_interval", 3)),
            float(self.config.get("map_idle_check_interval", 8)),
        )
        if now - self._idle_map_check_time < interval:
            return
        self._idle_map_check_time = now
        if not self._check_map_name(img, w, h):
            self._handle_map_block(on_status)

    def _loop_wait_interval(self):
        key = "monitor_active_interval" if self._popup_on else "monitor_idle_interval"
        default = 0.35 if self._popup_on else 0.70
        try:
            value = float(self.config.get(key, default))
        except Exception:
            value = default
        return max(0.15, min(value, 2.0))

    def process_frame(self, img, w, h, on_status):
        visible = self.is_popup_visible(img, w, h)
        if not visible:
            self._maybe_idle_map_check(img, w, h, on_status)
            if self._popup_on:
                self._reset_popup_state()
                on_status("等待題目…")
            return None

        force_map_check = bool(float(self.config.get("map_strict_mode", 1)))
        if not self._check_map_name(img, w, h, force=force_map_check):
            self._handle_map_block(on_status)
            return None

        if not self._popup_on:
            self._popup_on = True

        q_img = self._crop(img, w, h, self._question_region_key())
        opt_img = self._crop(img, w, h, "options_region")
        sig_img = q_img if self.mode == "sidestand" else self._quiz_signature_image(q_img, opt_img)
        ph = compute_phash(sig_img)
        if ph == 0 or ph == (1 << 64) - 1: return None
        sig_bits = _text_signature_bits(sig_img)
        now = time.time()
        cooldown = float(self.config.get("popup_recognition_cooldown", 2.0))
        force_recognition = self._force_next_recognition
        if force_recognition:
            self._force_next_recognition = False
        if not force_recognition and self._last_recognition_time and now - self._last_recognition_time < cooldown:
            return None
        same_threshold = float(self.config.get("popup_same_signature_threshold", 0.01))
        changed_from_ignored = False
        if (
            self._ignored_sig_bits is not None
            and _signature_distance(
                sig_bits,
                self._ignored_sig_bits,
            ) < float(self.config.get("popup_ignore_signature_threshold", 0.002))
        ):
            return None
        if self._ignored_sig_bits is not None:
            self._ignored_sig_bits = None
            changed_from_ignored = True
        if (
            not changed_from_ignored
            and not force_recognition
            and self._last_sig_bits is not None
            and _signature_distance(sig_bits, self._last_sig_bits) < same_threshold
        ):
            return None
        self._last_ph = ph
        self._last_sig_bits = sig_bits
        self._last_recognition_time = now
        on_status("偵測到題目…")

        if self.mode == "quiz4":
            return self._process_quiz4(img, w, h, q_img, ph, on_status)
        else:
            return self._process_sidestand(img, w, h, q_img, ph, on_status)

    def _process_quiz4(self, img, w, h, q_img, ph, on_status):
        full  = self._crop(img, w, h, "popup_full_region")
        q_img = self._crop(img, w, h, "question_region")
        opt_img = self._crop(img, w, h, "options_region")
        if not self.is_cropped_popup_visible(full):
            on_status("四選一裁切區不像完整問答框，略過")
            return None
        option_panel_signal = self.quiz4_option_panel_signal(opt_img)
        option_panel_threshold = float(self.config.get("quiz4_option_panel_threshold", 0.78))
        if option_panel_signal < option_panel_threshold:
            on_status(f"四選一選項區不像問答框暗底，略過（{option_panel_signal:.0%}/{option_panel_threshold:.0%}）")
            return None

        image_entry = self.db4.find_by_question_image(
            q_img,
            threshold=float(self.config.get("image_question_match_threshold", 0.88)),
        )
        if image_entry:
            score = image_entry.get("image_similarity", 0)
            on_status(f"截圖題庫命中（{score:.0%}）")
            return dict(
                image_entry,
                options=image_entry.get("options", []),
                source=f"截圖題庫 {score:.0%}",
                phash=ph,
            )

        on_status("OCR 辨識中…")
        q_text, options = ocr_parse_quiz(full, question_img=q_img, options_img=opt_img, on_detail=self._on_detail)

        gemini_key = self.config.get("gemini_api_key", "").strip()
        api_key    = self.config.get("api_key", "").strip()
        allow_api = bool(float(self.config.get("allow_paid_api_fallback", 0)))
        if allow_api and (not q_text or len([o for o in options if o.strip()]) < 2) and (gemini_key or api_key) and self._can_call_api(ph):
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
            capture_path = self._save_pending_capture(
                "quiz4", ph, full, q_img, opt_img,
                question="", options=options, reason="ocr_failed",
            )
            fallback_q = f"[OCR失敗] 四選一待校正 {ph & 0xffffffff:08x}"
            on_status("題目辨識失敗，已存待校正截圖")
            return {
                "question": fallback_q,
                "answer_idx": None,
                "answer_text": "",
                "options": options,
                "source": "辨識失敗截圖",
                "phash": ph,
                "capture_path": capture_path,
                "ocr_failed": True,
            }
        # 公告 / 結果畫面沒有選項，要求至少 2 個才視為有效題目
        if len([o for o in options if o.strip()]) < 2:
            capture_path = self._save_pending_capture(
                "quiz4", ph, full, q_img, opt_img,
                question=q_text, options=options, reason="options_incomplete",
            )
            pending_q = (
                q_text if self.config.get("trust_ocr_text_for_pending", 0)
                else f"[待校正] 四選一選項不足 {ph & 0xffffffff:08x}"
            )
            on_status("選項不足，已存待校正截圖")
            return {
                "question": pending_q,
                "answer_idx": None,
                "answer_text": "",
                "options": options,
                "source": "選項不足截圖",
                "phash": ph,
                "capture_path": capture_path,
                "ocr_failed": True,
                "recognized": q_text,
            }

        entry = self.db4.lookup(
            question=q_text,
            threshold=float(self.config.get("quiz4_match_threshold", 0.78)),
        )
        if entry:
            on_status("題庫命中（文字）")
            return dict(entry, options=options or entry.get("options",[]), source="題庫", phash=ph)

        on_status("題庫未找到")
        capture_path = self._save_pending_capture(
            "quiz4", ph, full, q_img, opt_img,
            question=q_text, options=options, reason="unknown",
        )
        pending_q = (
            q_text if self.config.get("trust_ocr_text_for_pending", 0)
            else f"[待校正] 四選一 {ph & 0xffffffff:08x}"
        )
        return {"question": pending_q, "answer_idx": None, "answer_text": "",
                "options": options, "source": "待校正截圖", "phash": ph,
                "capture_path": capture_path, "recognized": q_text}

    def _process_sidestand(self, img, w, h, q_img, ph, on_status):
        full  = self._crop(img, w, h, "sidestand_popup_full_region")
        q_img = self._crop(img, w, h, "sidestand_question_region")

        image_entry = self.dbs.find_by_question_image(
            q_img,
            threshold=float(self.config.get("image_question_match_threshold", 0.88)),
        )
        if image_entry:
            score = image_entry.get("image_similarity", 0)
            on_status(f"截圖題庫命中（{score:.0%}）")
            return dict(image_entry, phash=ph, recognized="", source=f"截圖題庫 {score:.0%}")

        on_status("OCR 辨識中…")
        q_text, _ = ocr_parse_quiz(full, question_img=q_img, on_detail=self._on_detail)

        gemini_key = self.config.get("gemini_api_key", "").strip()
        api_key    = self.config.get("api_key", "").strip()
        allow_api = bool(float(self.config.get("allow_paid_api_fallback", 0)))
        if allow_api and not q_text and (gemini_key or api_key) and self._can_call_api(ph):
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
            self._save_pending_capture(
                "sidestand", ph, full, q_img, None,
                question="", options=[], reason="ocr_failed_review",
            )
            on_status("選邊站 OCR 失敗，已保存截圖供活動後校正")
            return None
        # 選邊站題目不一定是疑問句；只要彈窗判定成立，就交給題庫相似度處理。

        threshold = self.config.get("match_threshold", 0.72)
        entry = self.dbs.lookup(q_text, threshold)
        if entry:
            on_status(f"命中（{entry['similarity']:.0%}）")
            return dict(entry, phash=ph, recognized=q_text)

        on_status("選邊站題庫未命中，已保存截圖供活動後校正")
        capture_path = self._save_pending_capture(
            "sidestand", ph, full, q_img, None,
            question=q_text, options=[], reason="unknown_review",
        )
        return {"question": q_text, "answer": None, "phash": ph, "recognized": q_text,
                "capture_path": capture_path, "review_only": True}

    def run(self, on_result, on_status, on_error, on_popup_gone=None, on_stopped=None, hwnd=None, title=""):
        self._stop.clear()
        if hwnd is None:
            windows = self.find_window()
            if not windows:
                on_error("找不到遊戲視窗，請確認遊戲已開啟"); return
            hwnd, title = windows[0]
        self.hwnd = hwnd
        on_status(f"已連接：{title}")
        try:
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
                self._stop.wait(self._loop_wait_interval())
        finally:
            if on_stopped:
                on_stopped()

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
        set_ocr_engine(self.config.get("ocr_engine", "windows"))
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
        self._last_status_msg = ""
        self._last_status_time = 0.0
        self._last_result_key = None
        self._last_result_time = 0.0
        self._last_notif_key = None
        self._last_notif_time = 0.0
        self._notif_pending = []
        self._notif_drain_scheduled = False
        self._notif_max_lines = 160
        self._detail_seen = {}
        self._refresh_jobs = set()
        self._window_size_poll_job = None
        self._last_polled_window_size = None
        self._ocr_preload_started = False
        self._tab_frames = {}
        self._built_tabs = set()

        self._apply_saved_window_size()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, lambda: (self.root.lift(), self.root.focus_force()))
        self._window_size_poll_job = self.root.after(1500, self._poll_window_size)
        if self.config.get("ocr_engine", "windows") in ("auto", "paddle"):
            self.root.after(1200, self._start_ocr_preload)

    # ── 設定 ──

    def _start_ocr_preload(self):
        if self._ocr_preload_started:
            return
        self._ocr_preload_started = True
        threading.Thread(target=self._preload_ocr_model, daemon=True).start()

    def _preload_ocr_model(self):
        try:
            self.root.after(0, self._add_notif, "PaddleOCR 模型背景載入中，第一次會比較久", "dim")
            _get_paddle_engine()
            global _PADDLE_OCR_AVAILABLE
            _PADDLE_OCR_AVAILABLE = True
            self.root.after(0, self._add_notif, "PaddleOCR 模型已載入，後續辨識會比較快", "ok")
        except Exception as e:
            global _PADDLE_OCR_WARNED
            _PADDLE_OCR_AVAILABLE = False
            _PADDLE_OCR_WARNED = True
            self.root.after(0, self._add_notif, f"PaddleOCR 載入失敗，改用 Windows OCR：{type(e).__name__}: {e}", "warn")

    def _load_config(self):
        cfg = dict(DEFAULT_CONFIG)
        if os.path.exists(CFG_FILE):
            try:
                with open(CFG_FILE, "r", encoding="utf-8") as f:
                    cfg.update(json.load(f))
            except Exception:
                pass
        if cfg.get("ocr_engine") == "auto":
            cfg["ocr_engine"] = "windows"
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

    def _remember_window_size(self):
        self._store_window_size()

    def _store_window_size(self):
        self.config["window_width"] = self.root.winfo_width()
        self.config["window_height"] = self.root.winfo_height()

    def _poll_window_size(self):
        try:
            size = (self.root.winfo_width(), self.root.winfo_height())
            if size != self._last_polled_window_size:
                self._last_polled_window_size = size
                self.config["window_width"], self.config["window_height"] = size
        finally:
            self._window_size_poll_job = self.root.after(1500, self._poll_window_size)

    def _on_close(self):
        self.detector.stop()
        self._coord_stop.set()
        self._nav_stop.set()
        if self._window_size_poll_job:
            try:
                self.root.after_cancel(self._window_size_poll_job)
            except Exception:
                pass
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

        self._main_tabs = ttk.Notebook(self.root)
        self._main_tabs.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        tab_defs = [
            ("main", " 答題 ", BG),
            ("db4", " 四選一題庫 ", BG2),
            ("pending4", " 四選一待校正 ", BG2),
            ("dbs", " 選邊站題庫 ", BG2),
            ("pending_side", " 選邊站待校正 ", BG2),
            ("cfg", " 設定 ", BG2),
        ]
        for key, title, bg in tab_defs:
            frame = tk.Frame(self._main_tabs, bg=bg, padx=6 if key == "main" else 0, pady=3 if key == "main" else 0)
            self._tab_frames[key] = frame
            self._main_tabs.add(frame, text=title)

        self._build_tab("main")
        self._main_tabs.bind("<<NotebookTabChanged>>", self._on_main_tab_changed)

    def _build_tab(self, key):
        if key in self._built_tabs:
            return
        frame = self._tab_frames.get(key)
        if frame is None:
            return
        if key == "main":
            self._build_main(frame)
        elif key == "db4":
            self._build_db4(frame)
        elif key == "pending4":
            self._build_pending4(frame)
        elif key == "dbs":
            self._build_dbs(frame)
        elif key == "pending_side":
            self._build_pending_dbs(frame)
        elif key == "cfg":
            self._build_cfg(frame)
        self._built_tabs.add(key)

    def _on_main_tab_changed(self, event=None):
        selected = self._main_tabs.select()
        for key, frame in self._tab_frames.items():
            if str(frame) == selected:
                self._build_tab(key)
                return

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
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.NONE,
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
        self._switch_mode("quiz4")

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
        ttk.Button(btn_row, text="手動新增", command=self._add_db4_manual).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_db4).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_db4).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊列可修改題目 / O/X）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.db4_tree.bind("<Double-Button-1>", self._edit_db4_entry)
        self._refresh_db4()

    def _build_pending4(self, f):
        cols = ("question","state","source")
        self.pending4_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        self.pending4_tree.heading("question", text="題目")
        self.pending4_tree.heading("state",    text="狀態")
        self.pending4_tree.heading("source",   text="來源")
        self.pending4_tree.column("question",  width=260)
        self.pending4_tree.column("state",     width=120)
        self.pending4_tree.column("source",    width=90)
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.pending4_tree.yview)
        self.pending4_tree.configure(yscrollcommand=vsb.set)
        self.pending4_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_pending4).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_pending4).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊校正，選好答案後自動移入正式題庫）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.pending4_tree.bind("<Double-Button-1>", self._edit_pending4_entry)
        self._refresh_pending4()

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
        ttk.Button(btn_row, text="手動新增", command=self._add_dbs_manual).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_dbs).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_dbs).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊列可修改答案）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.dbs_tree.bind("<Double-Button-1>", self._edit_dbs_entry)
        self._refresh_dbs()

    def _build_pending_dbs(self, f):
        cols = ("question","state")
        self.pending_dbs_tree = ttk.Treeview(f, columns=cols, show="headings", height=12)
        self.pending_dbs_tree.heading("question", text="題目")
        self.pending_dbs_tree.heading("state",   text="狀態")
        self.pending_dbs_tree.column("question", width=360)
        self.pending_dbs_tree.column("state",    width=90, anchor="center")
        vsb = ttk.Scrollbar(f, orient="vertical", command=self.pending_dbs_tree.yview)
        self.pending_dbs_tree.configure(yscrollcommand=vsb.set)
        self.pending_dbs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        btn_row = tk.Frame(f, bg=BG2)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="刪除選取", command=self._delete_pending_dbs).pack(side=tk.LEFT, padx=6, pady=4)
        ttk.Button(btn_row, text="重新整理", command=self._refresh_pending_dbs).pack(side=tk.LEFT)
        tk.Label(btn_row, text="（雙擊校正題目 / O/X，處理後自動移入正式題庫）", bg=BG2, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 8)).pack(side=tk.LEFT, padx=8)
        self.pending_dbs_tree.bind("<Double-Button-1>", self._edit_pending_dbs_entry)
        self._refresh_pending_dbs()

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

        def region_block(parent, title, rkey, hint=""):
            hdr = tk.Frame(parent, bg=BG2); hdr.pack(fill=tk.X)
            tk.Label(hdr, text=title, bg=BG2, fg=ACCENT,
                     font=("Microsoft JhengHei UI",10,"bold")).pack(side=tk.LEFT)
            tk.Button(hdr, text="框選", bg="#2C3E50", fg=TEXT_DIM, relief=tk.FLAT,
                      padx=6, pady=0, font=("Microsoft JhengHei UI",8),
                      activebackground="#3D5068",
                      command=lambda k=rkey: self._open_region_selector(k)
                      ).pack(side=tk.LEFT, padx=(8,0))
            tk.Button(hdr, text="圖片框選", bg="#2C3E50", fg=TEXT_DIM, relief=tk.FLAT,
                      padx=6, pady=0, font=("Microsoft JhengHei UI",8),
                      activebackground="#3D5068",
                      command=lambda k=rkey: self._open_region_selector(k, force_file=True)
                      ).pack(side=tk.LEFT, padx=(6,0))
            if hint:
                tk.Label(parent, text=hint, bg=BG2, fg=TEXT_DIM,
                         font=("Microsoft JhengHei UI",8)).pack(anchor="w", padx=4)

        def section(parent, title):
            box = tk.Frame(parent, bg=BG2, padx=8, pady=6,
                           highlightthickness=1, highlightbackground="#2E2E4A")
            box.pack(fill=tk.X, padx=6, pady=6)
            tk.Label(box, text=title, bg=BG2, fg=ACCENT,
                     font=("Microsoft JhengHei UI",10,"bold")).pack(anchor="w", pady=(0,4))
            return box

        def password_row(parent, label, key, width=28):
            r = tk.Frame(parent, bg=BG2); r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=label, bg=BG2, fg=TEXT_NORM,
                     font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar(value=self.config.get(key,""))
            self._cfg_vars[key] = var
            entry = tk.Entry(r, textvariable=var, width=width, show="*",
                             bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                             relief=tk.FLAT)
            entry.pack(side=tk.LEFT, padx=4)
            def toggle(btn=None):
                entry.configure(show="" if entry.cget("show")=="*" else "*")
                if btn: btn.configure(text="隱藏" if entry.cget("show")=="" else "顯示")
            btn = tk.Button(r, text="顯示", bg=BG2, fg=TEXT_DIM, relief=tk.FLAT, padx=4,
                            font=("Microsoft JhengHei UI",8), command=lambda: toggle(btn))
            btn.pack(side=tk.LEFT)

        nb = ttk.Notebook(f)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        pages = {}
        for key, title in [
            ("basic", "常用"),
            ("regions", "區域"),
            ("mapcoord", "地圖 / 座標"),
            ("api", "API / 進階"),
        ]:
            page = tk.Frame(nb, bg=BG2)
            nb.add(page, text=title)
            pages[key] = self._make_scrollable_frame(page, height=300)

        basic = pages["basic"]
        box = section(basic, "辨識與題庫")
        row(box, "OCR 引擎",          "ocr_engine", "windows / paddle / auto")
        row(box, "OCR 未命中信任文字", "trust_ocr_text_for_pending", "0=新題只存截圖待校正；1=把 OCR 文字當題目")
        row(box, "保存待校正截圖",   "save_pending_captures", "1=新題 / 失敗自動存圖；0=不存")
        row(box, "保存分區截圖",     "save_capture_regions", "1=同時保存題目區和選項區")
        tk.Label(box, text="彈窗門檻、相似度、監測間隔等細項已改用預設值；需要調整時再加回進階模式。",
                 bg=BG2, fg=TEXT_DIM, font=("Microsoft JhengHei UI",8),
                 wraplength=520, justify=tk.LEFT).pack(anchor="w", padx=4, pady=(4, 0))

        regions = pages["regions"]
        box = section(regions, "問答彈窗")
        region_block(box, "彈窗完整範圍", "popup_full_region",
                     hint="框整個問答彈窗，用來判斷彈窗和備用辨識")
        region_block(box, "題目文字區域", "question_region",
                     hint="辨識只看這個框；只框題目那一行，不要框到標題列、倒數、角色名或選項")
        region_block(box, "選項文字區域", "options_region",
                     hint="只框 1～4 的選項文字，不要框到題目或倒數時間")
        box = section(regions, "選邊站彈窗")
        region_block(box, "彈窗完整範圍（選邊站）", "sidestand_popup_full_region",
                     hint="選邊站視窗通常比四選一矮，請切到選邊站模式後重新框選整個彈窗")
        region_block(box, "題目文字區域（選邊站）", "sidestand_question_region",
                     hint="只框選邊站的題目那一行，不要框到標題列、倒數或角色名")
        box = section(regions, "地圖與座標區域")
        region_block(box, "右上座標區域", "coord_region",
                     hint="框選右上角角色座標，例如 4248,4024")
        region_block(box, "地圖名稱過濾（右上角）", "map_name_region",
                     hint="留空關鍵字欄位 = 不過濾")

        mapcoord = pages["mapcoord"]
        box = section(mapcoord, "活動場景")
        kw_row = tk.Frame(box, bg=BG2); kw_row.pack(fill=tk.X, pady=2)
        tk.Label(kw_row, text="  活動關鍵字（逗號分隔）", bg=BG2, fg=TEXT_NORM,
                 font=("Microsoft JhengHei UI",9), width=22, anchor="w").pack(side=tk.LEFT)
        kw_str = ",".join(self.config.get("quiz_map_keywords", []))
        self._kw_var = tk.StringVar(value=kw_str)
        tk.Entry(kw_row, textvariable=self._kw_var, width=22,
                 bg="#22223A", fg=TEXT_NORM, insertbackground=TEXT_NORM,
                 relief=tk.FLAT).pack(side=tk.LEFT, padx=4)
        tk.Label(box, text="地圖相似度、離場保護、座標模板等細項改用預設值；區域位置請到「區域」頁用框選設定。",
                 bg=BG2, fg=TEXT_DIM, font=("Microsoft JhengHei UI",8),
                 wraplength=520, justify=tk.LEFT).pack(anchor="w", padx=4, pady=(4, 0))
        box = section(mapcoord, "座標與導航")
        tk.Label(box, text="自動導航暫時擱置，這裡不再顯示手動微調數字。座標偵測仍可用下方「只測座標」確認。",
                 bg=BG2, fg=TEXT_DIM, font=("Microsoft JhengHei UI",8),
                 wraplength=520, justify=tk.LEFT).pack(anchor="w", padx=4, pady=(4, 0))

        api = pages["api"]
        box = section(api, "本機優先，付費 API 預設關閉")
        password_row(box, "GEMINI_API_KEY", "gemini_api_key")
        row(box, "Gemini 模型", "gemini_model", "")
        password_row(box, "ANTHROPIC_API_KEY", "api_key")
        row(box, "允許付費 API 備援", "allow_paid_api_fallback", "平常用 0；開 1 才會呼叫 Gemini / Claude")

        btn_wrap = tk.Frame(f, bg=BG2); btn_wrap.pack(fill=tk.X, padx=8, pady=6)
        save_row = tk.Frame(btn_wrap, bg=BG2); save_row.pack(fill=tk.X, pady=(0,4))
        test_row = tk.Frame(btn_wrap, bg=BG2); test_row.pack(fill=tk.X)
        ttk.Button(save_row, text="儲存設定", command=self._apply_cfg).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="用圖片檢查全部", command=self._test_image_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="只測問答辨識",   command=self._test_recognition_file).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="抓遊戲測問答",   command=self._test_recognition).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="只測座標",       command=self._test_coordinates).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="只測地圖名稱",   command=self._test_map_name).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="校準地圖圖片",   command=self._calibrate_map_image).pack(side=tk.LEFT, padx=6)
        ttk.Button(test_row, text="校準座標模板",   command=self._calibrate_coord_templates).pack(side=tk.LEFT, padx=6)

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
        now = time.time()
        key = (tag, m[:100])
        if now - self._detail_seen.get(key, 0.0) < 5.0:
            return
        self._detail_seen[key] = now
        if len(self._detail_seen) > 80:
            old_keys = sorted(self._detail_seen, key=self._detail_seen.get)[:20]
            for old_key in old_keys:
                self._detail_seen.pop(old_key, None)
        self.root.after(0, self._add_notif, m, tag)

    def _schedule_refresh(self, func, delay=120):
        name = getattr(func, "__name__", str(id(func)))
        if name in self._refresh_jobs:
            return
        self._refresh_jobs.add(name)

        def run():
            self._refresh_jobs.discard(name)
            func()

        self.root.after(delay, run)

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
            self.detector.force_next_recognition()
            self.start_btn.configure(text="停止監測", bg="#C0392B")
            self._set_status("已開始監測，正在檢查目前畫面是否有題目…")
            self._thread = threading.Thread(
                target=self.detector.run,
                args=(self._on_result, self._set_status, self._on_error),
                kwargs={
                    "on_popup_gone": self._on_popup_gone,
                    "on_stopped": self._on_monitor_stopped,
                    "hwnd": hwnd,
                    "title": title,
                },
                daemon=True,
            )
            self._thread.start()

    def _on_monitor_stopped(self):
        def update():
            self.start_btn.configure(text="開始監測", bg="#2ECC71")
        self.root.after(0, update)

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
        key = self._result_key(result)
        now = time.time()
        if key == self._last_result_key and now - self._last_result_time < 3.0:
            return
        self._last_result_key = key
        self._last_result_time = now
        self._current = result
        if not self._pinned: self.root.after(0, self._popup_window)
        self.root.after(0, self._show_result, result)
        mode = self._mode.get()
        if (mode == "quiz4" and result.get("answer_idx")) or (mode == "sidestand" and result.get("answer")):
            self.detector.ignore_current_popup()
        # 自動加入題庫（無答案的新題目）
        q = result.get("question", "")
        if q:
            dup_threshold = float(self.config.get("auto_add_duplicate_threshold", 0.80))
            merge_threshold = float(self.config.get("pending_merge_threshold", dup_threshold))
            if mode == "quiz4" and not result.get("answer_idx"):
                status = self.db4.add_pending(
                    result.get("phash") or 0,
                    q,
                    result.get("options", []),
                    threshold=merge_threshold,
                    capture_path=result.get("capture_path") or "",
                )
                if status == "merged":
                    self.root.after(0, self._add_notif, "四選一 → 這題像之前的待校正題，已合併，不新增一筆", "dim")
                    self._schedule_refresh(self._refresh_pending4)
                elif status == "added":
                    opt_count = quiz_option_count(result.get("options", []))
                    self.root.after(0, self._notify_auto_added, "quiz4", opt_count)
                    self._schedule_refresh(self._refresh_pending4)
                elif status == "answered":
                    self.root.after(0, self._add_notif, "四選一 → 類似題已經有答案，這次 OCR 錯字不寫入題庫", "dim")
            elif mode == "sidestand" and not result.get("answer"):
                if result.get("review_only") or not self.config.get("sidestand_auto_pending", 0):
                    self.root.after(
                        0,
                        self._add_notif,
                        "選邊站 → 未命中題庫，已保存截圖；活動後再校正，不自動加入題庫",
                        "warn",
                    )
                    return
                status = self.dbs.add_pending(
                    q,
                    threshold=merge_threshold,
                    capture_path=result.get("capture_path") or "",
                )
                if status == "added":
                    self.root.after(0, self._notify_auto_added, "sidestand")
                    self._schedule_refresh(self._refresh_pending_dbs)
                elif status == "merged":
                    self.root.after(0, self._add_notif, "選邊站 → 這題像之前的待填題，已略過，不新增一筆", "dim")
                    self._schedule_refresh(self._refresh_pending_dbs)
                elif status == "answered":
                    self.root.after(0, self._add_notif, "選邊站 → 類似題已經有答案，這次 OCR 錯字不寫入題庫", "dim")

    def _result_key(self, result):
        mode = self._mode.get()
        question = result.get("question", "")
        if mode == "quiz4":
            options = tuple((result.get("options") or [])[:4])
            return (
                mode,
                question,
                result.get("answer_idx"),
                result.get("answer_text", ""),
                options,
            )
        return (
            mode,
            question,
            result.get("answer"),
            result.get("recognized", ""),
        )

    def _add_notif(self, msg, tag="info"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        now = time.time()
        key = (tag, msg)
        if key == self._last_notif_key and now - self._last_notif_time < 1.5:
            return
        self._last_notif_key = key
        self._last_notif_time = now
        self._notif_pending.append((ts, msg, tag))
        if not self._notif_drain_scheduled:
            self._notif_drain_scheduled = True
            self.root.after(80, self._drain_notifs)

    def _drain_notifs(self):
        self._notif_drain_scheduled = False
        if not self._notif_pending:
            return
        pending = self._notif_pending[:40]
        del self._notif_pending[:40]
        self.notif_log.configure(state=tk.NORMAL)
        for ts, msg, tag in pending:
            self.notif_log.insert("end", f"[{ts}] ", "time")
            self.notif_log.insert("end", msg + "\n", tag)
        line_count = int(float(self.notif_log.index("end-1c").split(".")[0]))
        if line_count > self._notif_max_lines:
            self.notif_log.delete("1.0", f"{line_count - self._notif_max_lines + 1}.0")
        self.notif_log.see("end")
        self.notif_log.configure(state=tk.DISABLED)
        if self._notif_pending:
            self._notif_drain_scheduled = True
            self.root.after(120, self._drain_notifs)

    def _notify_auto_added(self, mode, opt_count=None):
        tab = "四選一待校正" if mode == "quiz4" else "選邊站待校正"
        self.status_lbl.configure(fg="#E67E22")
        if mode == "quiz4" and opt_count is not None and opt_count < 4:
            self.status_var.set(f"⚠ 新題目已暫存，但只有 {opt_count}/4 個選項，請活動後雙擊校正")
            self._add_notif(f"四選一 → 先暫存，選項只讀到 {opt_count}/4，活動後再校正", "warn")
        else:
            self.status_var.set(f"⚠ 未知題目已自動加入「{tab}」（尚無答案），請雙擊補充")
            self._add_notif(f"新題目已加入「{tab}」，目前還沒有答案", "warn")
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
        now = time.time()
        if msg == self._last_status_msg and now - self._last_status_time < 1.0:
            return
        self._last_status_msg = msg
        self._last_status_time = now
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
            recog    = result.get("recognized","")

            self.ans_num_var.set(str(idx) if idx else "?")
            self.ans_text_var.set(ans_text)
            if idx:
                self.quiz_answer_line_var.set(f"{idx}. {ans_text or '已命中答案'}")
            else:
                self.quiz_answer_line_var.set("尚未命中答案")
            display_q = question
            if _is_ocr_failed_placeholder(question) and recog:
                display_q = f"{question}｜OCR 參考：{recog[:48]}"
            self.q_var4.set(display_q[:90]+("…" if len(display_q)>90 else ""))
            if recog and _is_ocr_failed_placeholder(question):
                self.source_var4.set(f"來源：{source}｜OCR 只當參考")
            else:
                self.source_var4.set(f"來源：{source}" if source else "")

            for i,(var,color) in enumerate(zip(self.opt_vars, OPT_COLORS)):
                opt  = options[i] if i < len(options) else ""
                star = "★ " if idx == i+1 else "   "
                if opt or idx == i + 1:
                    var.set(f"{star}{i+1}. {opt}")
                else:
                    var.set("")

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
            elif recog and _is_ocr_failed_placeholder(question):
                self.source_vars.set(f"OCR 參考：{recog[:48]}")
            else:
                self.source_vars.set("未找到，可手動存入題庫")

            self.fix_btn.configure(state=tk.NORMAL if has_q else tk.DISABLED)

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
                            self._current.get("answer_text",""), self._current.get("options",[]),
                            capture_path=self._current.get("capture_path") or "")
            self._set_status(f"已存入四選一題庫：{q[:25]}…")
            self._refresh_db4()
            self._refresh_pending4()
            self.detector.ignore_current_popup()
        else:
            ans = self._current.get("answer")
            if ans:
                self.dbs.upsert(q, ans, old_question=q, capture_path=self._current.get("capture_path") or "")
                self._set_status(f"已存入選邊站題庫：{q[:25]}…")
                self._refresh_dbs()
                self._refresh_pending_dbs()
                self.detector.ignore_current_popup()
            else:
                self._set_status("請直接點畫面上的 O / X 設定答案")

    def _click_ox(self, ans):
        """點擊 O/X 按鈕直接設定選邊站答案並存入題庫。"""
        if not self._current or self._mode.get() != "sidestand": return
        q = self._current.get("question", "")
        if not q: return
        self._current["answer"] = ans
        self._show_result(self._current)
        self.dbs.upsert(q, ans, old_question=q, capture_path=self._current.get("capture_path") or "")
        self._set_status(f"答案 {ans} 已記錄：{q[:20]}…")
        self._add_notif(f"選邊站 → 答案確認 {ans}", "ok")
        self._refresh_dbs()
        self._refresh_pending_dbs()
        self.detector.ignore_current_popup()

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
                            self._current.get("options",[]),
                            capture_path=self._current.get("capture_path") or "")
            ans_t = self._current.get("answer_text","")
            self._set_status(f"答案 {idx} 已記錄：{q[:20]}…")
            self._add_notif(f"四選一 → 答案確認 {idx}. {ans_t[:18]}", "ok")
            self._refresh_db4()
            self._refresh_pending4()
            self.detector.ignore_current_popup()

    def _fix_answer(self):
        if not self._current:
            return
        if self._mode.get() == "quiz4":
            self._open_current_quiz4_editor()
        else:
            self._open_current_sidestand_editor()

    def _load_capture_preview_image(self, capture_path, region):
        if not capture_path:
            return None
        path = capture_path if region == "popup" else _capture_region_path(capture_path, region)
        if not path or not os.path.exists(path):
            return None
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            return None

    def _add_capture_preview(self, parent, entry, mode="quiz4"):
        paths = _entry_capture_paths(entry or {})
        if not paths:
            return
        capture_path = paths[-1]
        regions = [("question", "題目截圖", 420, 92)]
        if mode == "quiz4":
            regions.append(("options", "選項截圖", 420, 92))
        images = []
        for region, title, max_w, max_h in regions:
            img = self._load_capture_preview_image(capture_path, region)
            if img is not None:
                images.append((title, img, max_w, max_h))
        if not images:
            img = self._load_capture_preview_image(capture_path, "popup")
            if img is not None:
                images.append(("完整彈窗", img, 420, 140))
        if not images:
            return

        box = tk.Frame(parent, bg=BG)
        box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            box, text="當時保存的截圖", bg=BG, fg=TEXT_DIM,
            font=("Microsoft JhengHei UI", 9),
        ).pack(anchor="w")
        photos = []
        for title, img, max_w, max_h in images:
            row = tk.Frame(box, bg=BG2)
            row.pack(fill=tk.X, pady=(3, 0))
            photo = self._preview_photo(img, max_w=max_w, max_h=max_h, nearest=True)
            photos.append(photo)
            lbl = tk.Label(row, image=photo, bg=BG2)
            lbl.image = photo
            lbl.pack(side=tk.LEFT, padx=4, pady=4)
            tk.Label(
                row, text=title, bg=BG2, fg=TEXT_DIM,
                font=("Microsoft JhengHei UI", 9),
            ).pack(side=tk.LEFT, padx=(6, 4))
        box._preview_photos = photos

    def _open_current_quiz4_editor(self):
        cur = self._current or {}
        q = cur.get("question", "")
        opts = list(cur.get("options", []))

        win = tk.Toplevel(self.root)
        win.title("校正目前四選一"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(True, True)
        win.minsize(460, 360)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        self._add_capture_preview(body, cur, mode="quiz4")

        tk.Label(body, text="題目文字", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=3, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.insert("1.0", q)
        q_txt.pack(fill=tk.X, pady=(2, 8))

        tk.Label(body, text="選項和正確答案", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        chosen = tk.IntVar(value=cur.get("answer_idx") or 0)
        rows = []
        btn_frame = tk.Frame(body, bg=BG); btn_frame.pack(fill=tk.X, pady=(2, 8))
        for i in range(4):
            opt_text = opts[i] if i < len(opts) else ""
            row = tk.Frame(btn_frame, bg=BG)
            row.pack(fill=tk.X, pady=2)
            tk.Radiobutton(row, text=str(i + 1), variable=chosen, value=i + 1,
                           bg=BG, fg=OPT_COLORS[i], selectcolor="#222240",
                           font=("Microsoft JhengHei UI", 10), activebackground=BG).pack(side=tk.LEFT)
            var = tk.StringVar(value=opt_text)
            ent = tk.Entry(row, textvariable=var, bg=BG2, fg=TEXT_NORM,
                           insertbackground=TEXT_NORM, relief=tk.FLAT,
                           font=("Microsoft JhengHei UI", 10))
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=3)
            rows.append(var)

        hint = "可以先只修題目和選項；沒勾答案時會存成待校正。"
        tk.Label(body, text=hint, bg=BG, fg=TEXT_DIM, wraplength=430,
                 justify=tk.LEFT, font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(0, 8))

        def confirm():
            new_q = q_txt.get("1.0", "end").strip()
            new_opts = [var.get().strip() for var in rows]
            v = chosen.get()
            if not new_q:
                messagebox.showwarning("提示", "題目不能空白", parent=win)
                return
            ans_text = new_opts[v - 1] if v in (1, 2, 3, 4) and v <= len(new_opts) else ""
            cur["question"] = new_q
            cur["options"] = new_opts
            cur["answer_idx"] = v if v in (1, 2, 3, 4) else None
            cur["answer_text"] = ans_text
            self._current = cur
            self._show_result(cur)
            if cur.get("answer_idx"):
                self.db4.upsert(
                    cur.get("phash") or 0, new_q, cur["answer_idx"], ans_text, new_opts,
                    capture_path=cur.get("capture_path") or "",
                )
                self._set_status(f"已校正並存入四選一：{new_q[:20]}… → {cur['answer_idx']}")
            else:
                self.db4.add_pending(cur.get("phash") or 0, new_q, new_opts,
                                     threshold=float(self.config.get("pending_merge_threshold", 0.68)),
                                     capture_path=cur.get("capture_path") or "")
                self._set_status(f"已更新題目文字，暫存待校正：{new_q[:20]}…")
            self._refresh_db4()
            self._refresh_pending4()
            self.detector.ignore_current_popup()
            win.destroy()

        btn_row = tk.Frame(body, bg=BG); btn_row.pack(anchor="e")
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _open_current_sidestand_editor(self):
        cur = self._current or {}
        old_q = cur.get("question", "")

        win = tk.Toplevel(self.root)
        win.title("校正目前選邊站"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(True, True)
        win.minsize(420, 260)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        self._add_capture_preview(body, cur, mode="sidestand")
        tk.Label(body, text="題目 / 敘述文字", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=4, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.insert("1.0", old_q)
        q_txt.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        chosen = tk.StringVar(value=cur.get("answer") or "")
        ans_row = tk.Frame(body, bg=BG); ans_row.pack(fill=tk.X, pady=(0, 8))
        tk.Radiobutton(ans_row, text="O 正確", variable=chosen, value="O",
                       bg=BG, fg=COL_O, selectcolor="#222240",
                       font=("Microsoft JhengHei UI", 12, "bold"),
                       activebackground=BG).pack(side=tk.LEFT, padx=(0, 14))
        tk.Radiobutton(ans_row, text="X 錯誤", variable=chosen, value="X",
                       bg=BG, fg=COL_X, selectcolor="#222240",
                       font=("Microsoft JhengHei UI", 12, "bold"),
                       activebackground=BG).pack(side=tk.LEFT)

        def confirm():
            new_q = q_txt.get("1.0", "end").strip()
            ans = chosen.get() if chosen.get() in ("O", "X") else None
            if not new_q:
                messagebox.showwarning("提示", "題目不能空白", parent=win)
                return
            cur["question"] = new_q
            cur["recognized"] = new_q
            cur["answer"] = ans
            self._current = cur
            self._show_result(cur)
            if ans:
                self.dbs.upsert(new_q, ans, old_question=old_q, capture_path=cur.get("capture_path") or "")
                self._set_status(f"已校正並存入選邊站：{new_q[:20]}… → {ans}")
            else:
                self.dbs.add_pending(
                    new_q,
                    threshold=float(self.config.get("pending_merge_threshold", 0.68)),
                    capture_path=cur.get("capture_path") or "",
                )
                self._set_status(f"已更新選邊站題目，暫存待校正：{new_q[:20]}…")
            self._refresh_dbs()
            self._refresh_pending_dbs()
            self.detector.ignore_current_popup()
            win.destroy()

        btn_row = tk.Frame(body, bg=BG); btn_row.pack(anchor="e")
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _populate_tree_batched(self, tree, indices, mapping_name, make_item, batch_size=40):
        if not hasattr(self, "_tree_refresh_jobs"):
            self._tree_refresh_jobs = {}
        old_job = self._tree_refresh_jobs.pop(mapping_name, None)
        if old_job:
            try:
                self.root.after_cancel(old_job)
            except Exception:
                pass
        for item in tree.get_children():
            tree.delete(item)
        indices = list(indices)
        setattr(self, mapping_name, indices)

        def step(start=0):
            end = min(start + batch_size, len(indices))
            for real_idx in indices[start:end]:
                item = make_item(real_idx)
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], tuple):
                    values, tags = item
                else:
                    values, tags = item, ()
                tree.insert("", "end", tags=tags, values=values)
            if end < len(indices):
                self._tree_refresh_jobs[mapping_name] = self.root.after(1, lambda: step(end))
            else:
                self._tree_refresh_jobs.pop(mapping_name, None)

        step(0)

    def _refresh_db4(self):
        if not hasattr(self, "db4_tree"):
            return
        indices = self.db4.confirmed_indices()

        def make_item(real_idx):
            e = self.db4.entries[real_idx]
            idx  = e.get("answer_idx")
            t    = e.get("answer_text","")[:15]
            answer_label = f"{idx}. {t}" if idx else "（待填）"
            return (e.get("question","")[:28], answer_label, e.get("source","")[:8])

        self._populate_tree_batched(self.db4_tree, indices, "_db4_visible_indices", make_item)

    def _refresh_pending4(self):
        if not hasattr(self, "pending4_tree"):
            return
        self.pending4_tree.tag_configure("warn", foreground="#E67E22")
        indices = self.db4.pending_indices()

        def make_item(real_idx):
            e = self.db4.entries[real_idx]
            opt_count = quiz_option_count(e.get("options", []))
            answer_idx = e.get("answer_idx")
            state = "待選答案" if opt_count >= 4 else f"選項 {opt_count}/4"
            if answer_idx and opt_count < 4:
                state = f"已選 {answer_idx}，選項 {opt_count}/4"
            return (e.get("question","")[:34], state, e.get("source","")[:10]), ("warn",)

        self._populate_tree_batched(self.pending4_tree, indices, "_pending4_visible_indices", make_item)

    def _refresh_dbs(self):
        if not hasattr(self, "dbs_tree"):
            return
        indices = self.dbs.confirmed_indices()

        def make_item(real_idx):
            e = self.dbs.entries[real_idx]
            return (e.get("question","")[:50], e.get("answer"))

        self._populate_tree_batched(self.dbs_tree, indices, "_dbs_visible_indices", make_item)

    def _refresh_pending_dbs(self):
        if not hasattr(self, "pending_dbs_tree"):
            return
        self.pending_dbs_tree.tag_configure("warn", foreground="#E67E22")
        indices = self.dbs.pending_indices()

        def make_item(real_idx):
            e = self.dbs.entries[real_idx]
            return (e.get("question","")[:58], "待選 O/X"), ("warn",)

        self._populate_tree_batched(self.pending_dbs_tree, indices, "_pending_dbs_visible_indices", make_item)

    def _selected_real_index(self, tree, mapping_name):
        sel = tree.selection()
        if not sel:
            return None
        visible_idx = tree.index(sel[0])
        mapping = getattr(self, mapping_name, [])
        if visible_idx < 0 or visible_idx >= len(mapping):
            return None
        return mapping[visible_idx]

    def _quiz4_capture_images_from_path(self, path):
        base = path
        for suffix in ("_question.png", "_options.png", "_popup.png"):
            if base.endswith(suffix):
                base = base[:-len(suffix)]
                break
        q_path = base + "_question.png"
        opt_path = base + "_options.png"
        popup_path = base + "_popup.png"

        def load_if_exists(p):
            if p and os.path.exists(p):
                try:
                    return Image.open(p).convert("RGB")
                except Exception:
                    return None
            return None

        q_img = load_if_exists(q_path)
        opt_img = load_if_exists(opt_path)
        popup_img = load_if_exists(popup_path)
        if popup_img is None:
            try:
                popup_img = Image.open(path).convert("RGB")
            except Exception:
                popup_img = None
        capture_path = popup_path if os.path.exists(popup_path) else path
        return capture_path, popup_img, q_img, opt_img

    def _add_db4_manual(self):
        win = tk.Toplevel(self.root)
        win.title("手動新增四選一題庫")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.minsize(460, 360)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text="題目", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=3, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.pack(fill=tk.X, pady=(2, 8))

        tk.Label(body, text="選項與正確答案", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        chosen = tk.IntVar(value=0)
        rows = []
        btn_frame = tk.Frame(body, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(2, 8))
        for i in range(4):
            row = tk.Frame(btn_frame, bg=BG)
            row.pack(fill=tk.X, pady=2)
            tk.Radiobutton(row, text=str(i + 1), variable=chosen, value=i + 1,
                           bg=BG, fg=OPT_COLORS[i], selectcolor="#222240",
                           font=("Microsoft JhengHei UI", 10), activebackground=BG).pack(side=tk.LEFT)
            var = tk.StringVar(value="")
            ent = tk.Entry(row, textvariable=var, bg=BG2, fg=TEXT_NORM,
                           insertbackground=TEXT_NORM, relief=tk.FLAT,
                           font=("Microsoft JhengHei UI", 10))
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=3)
            rows.append(var)

        capture_path_holder = [""]
        ocr_status = tk.StringVar(value="")
        tk.Label(body, textvariable=ocr_status, bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9), anchor="w").pack(fill=tk.X, pady=(0, 4))

        def fill_from_image_file():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="選擇待校正截圖或分割截圖",
                filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
            )
            if not path:
                return
            capture_path, popup_img, q_img, opt_img = self._quiz4_capture_images_from_path(path)
            if q_img is None and opt_img is None and popup_img is None:
                messagebox.showwarning("提示", "這張圖無法讀取。", parent=win)
                return

            def compose_full():
                if popup_img is not None:
                    return popup_img
                imgs = [img for img in (q_img, opt_img) if img is not None]
                width = max(img.width for img in imgs)
                height = sum(img.height for img in imgs)
                canvas = Image.new("RGB", (width, height), (18, 18, 30))
                y = 0
                for img in imgs:
                    canvas.paste(img.convert("RGB"), (0, y))
                    y += img.height
                return canvas

            image_ocr_btn.configure(state=tk.DISABLED)
            ocr_status.set("正在從截圖辨識題目與選項…")

            def run():
                try:
                    q_text, ocr_opts = ocr_parse_quiz(
                        compose_full(),
                        question_img=q_img,
                        options_img=opt_img,
                        on_detail=None,
                    )

                    def update():
                        capture_path_holder[0] = capture_path
                        if q_text:
                            q_txt.delete("1.0", "end")
                            q_txt.insert("1.0", q_text)
                        for row_idx, opt in enumerate((ocr_opts or [])[:4]):
                            if opt:
                                rows[row_idx].set(opt)
                        count = quiz_option_count(ocr_opts or [])
                        ocr_status.set(f"截圖辨識完成：選項 {count}/4，請檢查並選答案。")
                        image_ocr_btn.configure(state=tk.NORMAL)

                    win.after(0, update)
                except Exception as e:
                    win.after(0, lambda: (
                        ocr_status.set(f"截圖辨識失敗：{type(e).__name__}"),
                        image_ocr_btn.configure(state=tk.NORMAL),
                    ))

            threading.Thread(target=run, daemon=True).start()

        def confirm():
            q = q_txt.get("1.0", "end").strip()
            opts = [var.get().strip() for var in rows]
            idx = chosen.get()
            if not q:
                messagebox.showwarning("提示", "請先輸入題目", parent=win)
                return
            if quiz_option_count(opts) < 4:
                messagebox.showwarning("提示", "請填滿 4 個選項", parent=win)
                return
            if idx not in (1, 2, 3, 4):
                messagebox.showwarning("提示", "請選擇正確答案", parent=win)
                return
            self.db4.upsert(0, q, idx, opts[idx - 1], opts, capture_path=capture_path_holder[0])
            self._refresh_db4()
            self._refresh_pending4()
            self._set_status(f"已手動新增四選一題庫：{q[:20]}…")
            win.destroy()

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(anchor="e")
        image_ocr_btn = tk.Button(btn_row, text="從截圖辨識填入", bg="#2C3E50", fg=TEXT_NORM, relief=tk.FLAT,
                                  padx=12, pady=4, font=("Microsoft JhengHei UI", 10),
                                  command=fill_from_image_file)
        image_ocr_btn.pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _add_dbs_manual(self):
        win = tk.Toplevel(self.root)
        win.title("手動新增選邊站題庫")
        win.configure(bg=BG)
        win.attributes("-topmost", True)
        win.resizable(True, True)
        win.minsize(440, 260)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text="題目", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=4, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.pack(fill=tk.BOTH, expand=True, pady=(2, 8))
        chosen = tk.StringVar(value="")
        row = tk.Frame(body, bg=BG)
        row.pack(fill=tk.X, pady=(0, 8))
        for ans, color, label in (("O", COL_O, "O（正確）"), ("X", COL_X, "X（錯誤）")):
            tk.Radiobutton(row, text=label, variable=chosen, value=ans,
                           bg=BG, fg=color, selectcolor="#222240",
                           font=("Microsoft JhengHei UI", 10), activebackground=BG).pack(side=tk.LEFT, padx=(0, 18))

        def confirm():
            q = q_txt.get("1.0", "end").strip()
            ans = chosen.get()
            if not q:
                messagebox.showwarning("提示", "請先輸入題目", parent=win)
                return
            if ans not in ("O", "X"):
                messagebox.showwarning("提示", "請選擇 O 或 X", parent=win)
                return
            self.dbs.upsert(q, ans, old_question=q, capture_path="")
            self._refresh_dbs()
            self._refresh_pending_dbs()
            self._set_status(f"已手動新增選邊站題庫：{q[:20]}…")
            win.destroy()

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(anchor="e")
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _edit_db4_entry(self, event):
        idx = self._selected_real_index(self.db4_tree, "_db4_visible_indices")
        if idx is None:
            return
        self._open_db4_entry_editor(idx)

    def _edit_pending4_entry(self, event):
        idx = self._selected_real_index(self.pending4_tree, "_pending4_visible_indices")
        if idx is None:
            return
        self._open_db4_entry_editor(idx)

    def _open_db4_entry_editor(self, idx):
        entry = self.db4.entries[idx]
        q    = entry.get("question", "")
        opts = entry.get("options", [])

        win = tk.Toplevel(self.root)
        win.title("校正四選一題庫"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(True, True)
        win.minsize(460, 360)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        self._add_capture_preview(body, entry, mode="quiz4")

        tk.Label(body, text="題目", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=3, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.insert("1.0", q)
        q_txt.pack(fill=tk.X, pady=(2, 8))

        tk.Label(body, text="選項和正確答案", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        chosen = tk.IntVar(value=entry.get("answer_idx") or 0)
        rows = []
        btn_frame = tk.Frame(body, bg=BG); btn_frame.pack(fill=tk.X, pady=(2, 8))
        for i in range(4):
            opt_text = opts[i] if i < len(opts) else f"選項 {i+1}"
            row = tk.Frame(btn_frame, bg=BG)
            row.pack(fill=tk.X, pady=2)
            tk.Radiobutton(row, text=str(i + 1), variable=chosen, value=i + 1,
                           bg=BG, fg=OPT_COLORS[i], selectcolor="#222240",
                           font=("Microsoft JhengHei UI", 10), activebackground=BG).pack(side=tk.LEFT)
            var = tk.StringVar(value=opt_text)
            ent = tk.Entry(row, textvariable=var, bg=BG2, fg=TEXT_NORM,
                           insertbackground=TEXT_NORM, relief=tk.FLAT,
                           font=("Microsoft JhengHei UI", 10))
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), ipady=3)
            rows.append(var)

        hint = "活動中可以先讓題目暫存；活動後在這裡修題目、選項，再勾正確答案。"
        tk.Label(body, text=hint, bg=BG, fg=TEXT_DIM, wraplength=430,
                 justify=tk.LEFT, font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(0, 8))

        def confirm():
            v = chosen.get()
            new_q = q_txt.get("1.0", "end").strip()
            new_opts = [var.get().strip() for var in rows]
            if not new_q:
                messagebox.showwarning("提示", "題目不能空白", parent=win)
                return
            if v not in (1, 2, 3, 4):
                messagebox.showwarning("提示", "請選擇正確答案", parent=win)
                return
            ans_text = new_opts[v-1] if v <= len(new_opts) else ""
            target = self.db4.entries[idx]
            self.db4.entries[idx]["question"] = new_q
            self.db4.entries[idx]["options"] = new_opts
            self.db4.entries[idx]["answer_idx"] = v
            self.db4.entries[idx]["answer_text"] = ans_text
            self.db4.entries[idx]["source"] = "手動"
            paths = _entry_capture_paths(target)
            if paths:
                target["capture_path"] = paths[-1]
                target["captures"] = [paths[-1]]
            self.db4._save()
            self._refresh_db4()
            self._refresh_pending4()
            self._set_status(f"已校正：{new_q[:20]}… → {v}")
            win.destroy()

        btn_row = tk.Frame(body, bg=BG); btn_row.pack(anchor="e")
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _edit_dbs_entry(self, event):
        idx = self._selected_real_index(self.dbs_tree, "_dbs_visible_indices")
        if idx is None:
            return
        self._open_dbs_entry_editor(idx)

    def _edit_pending_dbs_entry(self, event):
        idx = self._selected_real_index(self.pending_dbs_tree, "_pending_dbs_visible_indices")
        if idx is None:
            return
        self._open_dbs_entry_editor(idx)

    def _open_dbs_entry_editor(self, idx):
        entry = self.dbs.entries[idx]
        q     = entry.get("question", "")
        current_answer = entry.get("answer") if entry.get("answer") in ("O", "X") else ""

        win = tk.Toplevel(self.root)
        win.title("校正選邊站題庫"); win.configure(bg=BG)
        win.attributes("-topmost", True); win.resizable(True, True)
        win.minsize(440, 300)

        body = tk.Frame(win, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)
        self._add_capture_preview(body, entry, mode="sidestand")

        tk.Label(body, text="題目", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        q_txt = tk.Text(body, height=5, bg=BG2, fg=TEXT_NORM, insertbackground=TEXT_NORM,
                        relief=tk.FLAT, wrap=tk.WORD, font=("Microsoft JhengHei UI", 10))
        q_txt.insert("1.0", q)
        q_txt.pack(fill=tk.BOTH, expand=True, pady=(2, 8))

        tk.Label(body, text="答案", bg=BG, fg=TEXT_DIM,
                 font=("Microsoft JhengHei UI", 9)).pack(anchor="w")
        chosen = tk.StringVar(value=current_answer)
        ans_row = tk.Frame(body, bg=BG)
        ans_row.pack(fill=tk.X, pady=(2, 8))
        for label, value, color in [
            ("O（正確）", "O", COL_O),
            ("X（錯誤）", "X", COL_X),
            ("待校正", "", TEXT_DIM),
        ]:
            tk.Radiobutton(
                ans_row, text=label, variable=chosen, value=value,
                bg=BG, fg=color, selectcolor="#222240",
                font=("Microsoft JhengHei UI", 10), activebackground=BG,
            ).pack(side=tk.LEFT, padx=(0, 14))

        hint = "如果 OCR 題目有錯字，直接在這裡修正；答案選 O 或 X 後會進正式題庫。"
        tk.Label(body, text=hint, bg=BG, fg=TEXT_DIM, wraplength=410,
                 justify=tk.LEFT, font=("Microsoft JhengHei UI", 9)).pack(anchor="w", pady=(0, 8))

        def confirm():
            new_q = q_txt.get("1.0", "end").strip()
            if not new_q:
                messagebox.showwarning("提示", "題目不能空白", parent=win)
                return
            answer = chosen.get() or None
            self.dbs.entries[idx]["question"] = new_q
            self.dbs.entries[idx]["answer"] = answer
            self.dbs._save()
            self._refresh_dbs()
            self._refresh_pending_dbs()
            self._set_status(f"已校正選邊站：{new_q[:20]}… → {answer or '待校正'}")
            win.destroy()

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(anchor="e")
        tk.Button(btn_row, text="確認", bg=ACCENT, fg="white", relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="取消", bg=BG2, fg=TEXT_NORM, relief=tk.FLAT,
                  padx=16, pady=4, font=("Microsoft JhengHei UI", 10),
                  command=win.destroy).pack(side=tk.LEFT)

    def _delete_db4(self):
        sel = self.db4_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆四選一題庫資料？"):
            idx = self._selected_real_index(self.db4_tree, "_db4_visible_indices")
            if idx is not None:
                self.db4.delete(idx)
            self._refresh_db4()
            self._refresh_pending4()

    def _delete_pending4(self):
        sel = self.pending4_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆四選一待校正資料？"):
            idx = self._selected_real_index(self.pending4_tree, "_pending4_visible_indices")
            if idx is not None:
                self.db4.delete(idx)
            self._refresh_db4()
            self._refresh_pending4()

    def _delete_dbs(self):
        sel = self.dbs_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆選邊站題庫資料？"):
            idx = self._selected_real_index(self.dbs_tree, "_dbs_visible_indices")
            if idx is not None:
                self.dbs.delete(idx)
            self._refresh_dbs()
            self._refresh_pending_dbs()

    def _delete_pending_dbs(self):
        sel = self.pending_dbs_tree.selection()
        if not sel: return
        if messagebox.askyesno("刪除","確定要刪除這筆選邊站待校正資料？"):
            idx = self._selected_real_index(self.pending_dbs_tree, "_pending_dbs_visible_indices")
            if idx is not None:
                self.dbs.delete(idx)
            self._refresh_dbs()
            self._refresh_pending_dbs()

    def _apply_cfg(self):
        _str_keys = {"api_key", "gemini_api_key", "gemini_model", "ocr_engine"}
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
        set_ocr_engine(self.config.get("ocr_engine", "windows"))
        self.detector.config = self.config
        self._save_config()
        messagebox.showinfo("設定","設定已儲存")

    def _open_region_selector(self, region_key, force_file=False):
        """截遊戲畫面（或讀截圖檔案），讓使用者拖曳框選區域，自動寫回設定欄位。"""
        img = None
        frame_top = 0
        # 預設用遊戲視窗；按「圖片框選」時直接讀截圖檔案。
        windows = [] if force_file else self.detector.find_window()
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
                img, frame_top = strip_window_frame_if_present(img)
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
        source_hint = "截圖檔已自動去掉上方標題列。" if frame_top else "拖曳滑鼠框選目標區域，放開後座標自動填入（記得儲存設定）"
        tk.Label(win, text=source_hint,
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
            if region_key not in self.config or not isinstance(self.config.get(region_key), dict):
                self.config[region_key] = {}
            for sub, val in [("left",rl),("top",rt),("right",rr),("bottom",rb)]:
                self.config[region_key][sub] = val
                k = f"{region_key}.{sub}"
                if k in self._cfg_vars:
                    self._cfg_vars[k].set(str(val))
            self.detector.config = self.config
            try:
                self._save_config()
            except Exception:
                pass
            result_lbl.configure(
                text="已套用並儲存這個框選區域")

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
                text = ocr_map_name_image(map_crop).strip()
                clean_text = clean_map_name_text(text)
                keywords = self.config.get("quiz_map_keywords", [])
                if keywords:
                    clean_keywords = normalize_map_keywords(keywords)
                    text_kw, text_score = match_map_keyword(clean_text, clean_keywords)
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
                        f"文字比對：{text_kw or '未命中'} {text_score:.0%}\n"
                        f"圖片比對：{best_kw or '未校準'} {best_sim:.0%} / 門檻 {threshold:.0%}\n"
                    )
                    text_matched = bool(text_kw) and text_score >= 0.80
                    matched = text_matched or image_matched
                    if text_matched:
                        kw_status = "✓ 文字已命中地圖名稱 → 辨識啟動（圖片分數只當參考）"
                    elif image_matched:
                        kw_status = "✓ 圖片比對命中 → 辨識啟動"
                    else:
                        kw_status = "✗ 文字和圖片都未命中 → 辨識略過"
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
        frame_top = 0
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
            try:
                picked = self._pick_screenshot_file("選擇遊戲截圖（座標測試）", strip_frame=True)
                if not picked:
                    return
                img, w, h, path, frame_top = picked
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

    def _pick_screenshot_file(self, title="選擇遊戲截圖", strip_frame=True):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("圖片", "*.png *.jpg *.jpeg *.bmp"), ("所有檔案", "*.*")],
        )
        if not path:
            return None
        img = Image.open(path).convert("RGB")
        frame_top = 0
        if strip_frame:
            img, frame_top = strip_window_frame_if_present(img)
        w, h = img.size
        return img, w, h, path, frame_top

    def _preview_photo(self, pil_img, max_w=360, max_h=130, nearest=False):
        iw, ih = pil_img.size
        scale = min(max_w / max(iw, 1), max_h / max(ih, 1), 1.0)
        resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
        preview = pil_img.resize(
            (max(1, int(iw * scale)), max(1, int(ih * scale))),
            resample,
        )
        return ImageTk.PhotoImage(preview)

    def _test_image_all(self):
        picked = self._pick_screenshot_file("選擇遊戲截圖（圖片綜合測試）", strip_frame=True)
        if not picked:
            return
        img, w, h, path, frame_top = picked

        win = tk.Toplevel(self.root)
        win.title("圖片綜合測試"); win.configure(bg=BG)
        win.resizable(True, True); win.attributes("-topmost", True)
        win.minsize(620, 520)

        tk.Label(win, text="圖片綜合測試", bg=BG, fg=ACCENT,
                 font=("Microsoft JhengHei UI", 12, "bold")).pack(pady=(8, 2))
        status_lbl = tk.Label(win, text="辨識中…", bg=BG, fg=TEXT_DIM,
                              font=("Microsoft JhengHei UI", 9))
        status_lbl.pack()

        crop_frame = tk.Frame(win, bg=BG)
        crop_frame.pack(fill=tk.X, padx=10, pady=6)
        crop_labels = {}
        mode = self._mode.get()
        crop_items = [
            ("question_region", "題目區"),
            ("map_name_region", "地圖區"),
            ("coord_region", "座標區"),
        ]
        if mode == "quiz4":
            crop_items.insert(1, ("options_region", "選項區"))
        for idx, (key, title) in enumerate(crop_items):
            cell = tk.Frame(crop_frame, bg=BG)
            cell.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=4, pady=4)
            tk.Label(cell, text=title, bg=BG, fg=TEXT_DIM,
                     font=("Microsoft JhengHei UI", 8)).pack(anchor="w")
            lbl = tk.Label(cell, bg="#111122", fg=TEXT_DIM, relief=tk.SUNKEN,
                           text="（預覽）", font=("Microsoft JhengHei UI", 8))
            lbl.pack(fill=tk.X, ipadx=4, ipady=4)
            crop_labels[key] = lbl
        crop_frame.columnconfigure(0, weight=1)
        crop_frame.columnconfigure(1, weight=1)

        result_txt = tk.Text(win, bg=BG2, fg=TEXT_NORM, height=14, width=76,
                             font=("Microsoft JhengHei UI", 10),
                             relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD)
        result_txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        result_txt.tag_configure("head", foreground="#FFAA00",
                                 font=("Microsoft JhengHei UI", 10, "bold"))
        result_txt.tag_configure("warn", foreground="#E67E22")
        result_txt.tag_configure("ok", foreground="#2ECC71")
        result_txt.tag_configure("dim", foreground=TEXT_DIM)

        def append(text, tag=None):
            result_txt.configure(state=tk.NORMAL)
            result_txt.insert("end", text, tag) if tag else result_txt.insert("end", text)
            result_txt.configure(state=tk.DISABLED)

        def run():
            try:
                region_keys = {
                    "question_region": "sidestand_question_region" if mode == "sidestand" else "question_region",
                    "options_region": "options_region",
                    "popup_full_region": "sidestand_popup_full_region" if mode == "sidestand" else "popup_full_region",
                    "map_name_region": "map_name_region",
                    "coord_region": "coord_region",
                }
                crops = {
                    label_key: self.detector._crop(img, w, h, region_keys[label_key])
                    for label_key in region_keys
                }
                detail_cb = lambda msg: win.after(0, append, f"  ⚠ {msg}\n", "warn")
                if mode == "quiz4":
                    q_text, options = ocr_parse_quiz(
                        crops["popup_full_region"],
                        question_img=crops["question_region"],
                        options_img=crops["options_region"],
                        on_detail=detail_cb,
                    )
                    side_entry = None
                else:
                    q_text, _ = ocr_parse_quiz(
                        crops["popup_full_region"],
                        question_img=crops["question_region"],
                        on_detail=detail_cb,
                    )
                    options = []
                    side_entry = self.dbs.lookup(
                        q_text,
                        self.config.get("match_threshold", 0.72),
                    ) if q_text else None
                map_raw = ocr_map_name_image(crops["map_name_region"]).strip()
                map_clean = clean_map_name_text(map_raw)
                map_keywords = self.config.get("quiz_map_keywords", [])
                map_match_lines = []
                if map_keywords:
                    clean_keywords = normalize_map_keywords(map_keywords)
                    text_kw, text_score = match_map_keyword(map_clean, clean_keywords)
                    best_kw = ""
                    best_sim = 0.0
                    for kw in clean_keywords:
                        ref = load_map_reference(kw)
                        if not ref:
                            continue
                        sim = image_similarity(crops["map_name_region"], ref)
                        if sim > best_sim:
                            best_kw, best_sim = kw, sim
                    map_threshold = float(self.config.get("map_image_match_threshold", 0.78))
                    text_matched = bool(text_kw) and text_score >= 0.80
                    image_matched = bool(best_kw) and best_sim >= map_threshold
                    map_match_lines.append((
                        f"文字比對：{text_kw or '未命中'} {text_score:.0%}\n",
                        "ok" if text_matched else "warn",
                    ))
                    map_match_lines.append((
                        f"圖片比對：{best_kw or '未校準'} {best_sim:.0%} / 門檻 {map_threshold:.0%}\n",
                        "ok" if image_matched else "dim",
                    ))
                    if text_matched:
                        map_match_lines.append(("判斷：文字已命中，圖片分數只當參考。\n", "ok"))
                    elif image_matched:
                        map_match_lines.append(("判斷：文字未命中，但圖片備援命中。\n", "ok"))
                    else:
                        map_match_lines.append(("判斷：文字和圖片都未命中，會略過辨識。\n", "warn"))
                else:
                    map_match_lines.append(("關鍵字未設定，目前不會用地圖名稱過濾。\n", "dim"))
                detector = GameDetector(self.config, self.db4, self.dbs)
                coord, coord_raw = detector.read_coordinates(img, w, h)
                coord_used_fallback = False
                if not coord:
                    coord, coord_raw = detector.read_coordinates(img, w, h, try_fallback_regions=True)
                    coord_used_fallback = bool(coord)
                brightness = self.detector.sample_brightness(img, w, h)
                threshold = self.config.get("popup_brightness_threshold", 80)
                opt_count = quiz_option_count(options)

                photos = {
                    "question_region": self._preview_photo(crops["question_region"], 285, 90, nearest=True),
                    "map_name_region": self._preview_photo(crops["map_name_region"], 285, 90, nearest=True),
                    "coord_region": self._preview_photo(crops["coord_region"], 285, 90, nearest=True),
                }
                if mode == "quiz4":
                    photos["options_region"] = self._preview_photo(crops["options_region"], 285, 90, nearest=True)

                def update():
                    for key, photo in photos.items():
                        crop_labels[key].configure(image=photo, text="")
                        crop_labels[key].image = photo

                    append(f"檔案：{os.path.basename(path)}\n", "dim")
                    append(f"OCR 引擎：{ocr_engine_label()}\n", "dim")
                    if frame_top:
                        append(f"已自動去掉上方標題列 {frame_top}px。\n", "dim")
                    append(f"彈窗亮度：{brightness:.1f} / 門檻 {threshold}", "head")
                    append("  → 像是彈窗\n" if brightness < threshold else "  → 可能不是彈窗\n",
                           "ok" if brightness < threshold else "warn")

                    if mode == "quiz4":
                        append("\n四選一辨識\n", "head")
                        append(f"題目：{q_text or '（空，請調整題目文字區域）'}\n",
                               None if q_text else "warn")
                        append(f"選項完整度：{opt_count}/4\n", "ok" if opt_count == 4 else "warn")
                        for i in range(4):
                            opt = options[i] if i < len(options) else ""
                            append(f"  {i + 1}. {opt or '（空）'}\n",
                                   None if opt else "warn")
                    else:
                        append("\n選邊站 / 是非題辨識\n", "head")
                        append(f"敘述：{q_text or '（空，請調整題目文字區域）'}\n",
                               None if q_text else "warn")
                        if side_entry:
                            append(
                                f"題庫判斷：{side_entry.get('answer') or '（待填）'}"
                                f"（相似度 {side_entry.get('similarity', 0):.0%}）\n",
                                "ok" if side_entry.get("answer") else "warn",
                            )
                        elif q_text:
                            append("題庫未找到此題\n", "warn")

                    append("\n地圖名稱\n", "head")
                    append(f"OCR：{map_raw or '（空）'}\n")
                    append(f"清理後：{map_clean or '（空）'}\n",
                           None if map_clean else "warn")
                    for line, tag in map_match_lines:
                        append(line, tag)

                    append("\n座標\n", "head")
                    append(f"原文：{coord_raw or '（空）'}\n")
                    append(
                        f"解析：{coord[0]},{coord[1]}\n" if coord else "解析：失敗\n",
                        "ok" if coord else "warn",
                    )
                    if coord_used_fallback:
                        append("目前設定的座標框沒讀到，改用右上角候選範圍才讀到。\n", "warn")
                    append("\n如果上方某一區預覽框不是你要的文字，請到「設定 → 區域」重新框選該區域。\n", "dim")
                    status_lbl.configure(text="完成")

                win.after(0, update)
            except Exception as e:
                win.after(0, lambda: status_lbl.configure(text=f"錯誤：{e}"))

        threading.Thread(target=run, daemon=True).start()

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
                full_img = self.detector._crop(img, w, h, self.detector._popup_region_key())
                q_img    = self.detector._crop(img, w, h, self.detector._question_region_key())
                opt_img  = self.detector._crop(img, w, h, "options_region")
                pw, ph2  = full_img.size
                scale    = min(380/pw, 1.0)
                preview  = full_img.resize((int(pw*scale), max(1,int(ph2*scale))), Image.Resampling.LANCZOS)
                tk_img   = ImageTk.PhotoImage(preview)

                def update_ui():
                    preview_lbl.configure(image=tk_img, text=""); preview_lbl.image = tk_img
                    _append(f"{label}\n", "dim")

                    # 亮度資訊（即時截圖才有）
                    if brightness is not None:
                        edge = self.detector.popup_edge_strength(img, w, h)
                        edge_threshold = float(self.config.get("popup_edge_threshold", 35))
                        frame_signal = self.detector.popup_frame_signal(img, w, h)
                        frame_key = "sidestand_popup_frame_threshold" if mode == "sidestand" else "quiz4_popup_frame_threshold"
                        frame_threshold = float(self.config.get(frame_key, 0.35))
                        bottom_signal = self.detector.popup_bottom_frame_signal(img, w, h)
                        bottom_threshold = float(self.config.get("quiz4_popup_bottom_frame_threshold", 0.35))
                        bottom_info = f"底框：{bottom_signal:.2f}/{bottom_threshold:.2f}  " if mode != "sidestand" else ""
                        option_panel_info = ""
                        if mode == "quiz4":
                            option_panel_signal = self.detector.quiz4_option_panel_signal(opt_img)
                            option_panel_threshold = float(self.config.get("quiz4_option_panel_threshold", 0.78))
                            option_panel_info = f"選項暗底：{option_panel_signal:.0%}/{option_panel_threshold:.0%}  "
                        margin = float(self.config.get("popup_brightness_margin", 18))
                        text_signal = self.detector.popup_text_signal(img, w, h)
                        popup_ok = self.detector.is_popup_visible(img, w, h)
                        _append(
                            f"亮度：{brightness:.1f}  門檻：{threshold}  "
                            f"框線：{edge:.1f}/{edge_threshold:.1f}  "
                            f"框體：{frame_signal:.2f}/{frame_threshold:.2f}  "
                            f"{bottom_info}"
                            f"{option_panel_info}"
                            f"文字參考：{text_signal:.3f}  強制通過：{margin}\n"
                        )
                        _append("→ 彈窗已偵測到\n","ok") if popup_ok else _append("→ 未偵測到彈窗\n","warn")
                        if not popup_ok:
                            status_lbl.configure(text="完成（彈窗未出現）"); return
                    else:
                        _append("→ 檔案模式，直接辨識\n","dim")
                    _append(f"OCR 引擎：{ocr_engine_label()}\n", "dim")

                    def _detail(msg):
                        win.after(0, lambda m=msg: _append(f"  ⚠ {m}\n", "warn"))

                    if mode == "quiz4":
                        q_text, options = "", []
                        q_text, options = ocr_parse_quiz(full_img, question_img=q_img, options_img=opt_img, on_detail=_detail)
                        src = ocr_engine_label()
                        _append(f"\n辨識方式：{src}\n","dim")
                        _append("測試模式只跑本機 OCR，不呼叫 Gemini / Claude。\n","dim")
                        _append("題目：","head"); _append(f"{q_text or '（無法辨識）'}\n")
                        _append("選項：\n","head")
                        for i,opt in enumerate(options[:4]): _append(f"  {i+1}. {opt}\n")
                    else:
                        q_text = ""
                        q_text, _ = ocr_parse_quiz(full_img, question_img=q_img, on_detail=_detail)
                        src = ocr_engine_label()
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

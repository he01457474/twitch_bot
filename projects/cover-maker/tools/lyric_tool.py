#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 翻唱歌詞工具 — 搜尋歌詞、轉 SRT、簡轉繁、換歌手名"""

import re
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import requests
import opencc

BASE_DIR  = Path(__file__).parent.parent
OUT_DIR   = BASE_DIR / 'output'
CFG_FILE  = BASE_DIR / 'config.json'
LRCLIB    = 'https://lrclib.net/api'
HEADERS   = {'User-Agent': 'LyricTool/1.0 (AI Cover Maker)'}

converter = opencc.OpenCC('s2twp')  # 簡體 → 繁體台灣

# ── 設定讀寫 ──────────────────────────────────────────────────
def load_cfg() -> dict:
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text('utf-8'))
        except Exception:
            pass
    return {}

def save_cfg(cfg: dict):
    CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')

# ── LRC / SRT 處理 ────────────────────────────────────────────
def lrc_time_to_srt(ts: str) -> str:
    """[mm:ss.xx] → hh:mm:ss,ms"""
    m = re.match(r'(\d+):(\d+)[.:](\d+)', ts)
    if not m:
        return '00:00:00,000'
    mm, ss, cs = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = mm // 60
    mm = mm % 60
    ms = cs * 10 if len(m.group(3)) == 2 else cs
    return f'{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}'

def lrc_to_srt(lrc: str, cover_artist: str, orig_artist: str) -> str:
    """LRC 轉 SRT，順帶簡轉繁、換歌手名"""
    lines = []
    for line in lrc.splitlines():
        m = re.match(r'\[(\d+:\d+[.:]\d+)\](.*)', line)
        if m:
            lines.append((m.group(1), m.group(2).strip()))

    if not lines:
        return ''

    srt_parts = []
    for i, (ts, text) in enumerate(lines):
        start = lrc_time_to_srt(ts)
        if i + 1 < len(lines):
            end = lrc_time_to_srt(lines[i + 1][0])
        else:
            # 最後一行結束時間 +3 秒
            def add3(t):
                h, m, rest = t.split(':')
                s, ms = rest.split(',')
                total_ms = int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms) + 3000
                hh = total_ms // 3600000; total_ms %= 3600000
                mm = total_ms // 60000;   total_ms %= 60000
                ss = total_ms // 1000;    total_ms %= 1000
                return f'{hh:02d}:{mm:02d}:{ss:02d},{total_ms:03d}'
            end = add3(start)

        text_tw = converter.convert(text)
        # 換歌手名（若文字中包含原唱名稱就替換）
        if orig_artist and orig_artist in text_tw:
            text_tw = text_tw.replace(orig_artist, cover_artist)

        if text_tw:
            srt_parts.append(f'{i + 1}\n{start} --> {end}\n{text_tw}')

    return '\n\n'.join(srt_parts)

# ── LRCLIB API ────────────────────────────────────────────────
def search_lrclib(song: str, artist: str) -> list[dict]:
    params = {'q': f'{artist} {song}'.strip()} if artist else {'q': song}
    r = requests.get(f'{LRCLIB}/search', params=params, headers=HEADERS, timeout=10)
    r.raise_for_status()
    results = r.json()
    # 過濾有時間軸歌詞的結果
    return [x for x in results if x.get('syncedLyrics')]

def get_synced_lyrics(lrclib_id: int) -> str:
    r = requests.get(f'{LRCLIB}/get/{lrclib_id}', headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json().get('syncedLyrics', '')

# ── GUI ───────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('AI 翻唱歌詞工具')
        self.resizable(False, False)
        self.cfg = load_cfg()
        self.results: list[dict] = []
        self._build()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build(self):
        pad = {'padx': 10, 'pady': 4}

        # ── 搜尋區 ──
        frm_search = ttk.LabelFrame(self, text='搜尋歌詞', padding=8)
        frm_search.grid(row=0, column=0, sticky='ew', **pad, pady=(10, 4))

        ttk.Label(frm_search, text='歌名').grid(row=0, column=0, sticky='w')
        self.var_song = tk.StringVar()
        ttk.Entry(frm_search, textvariable=self.var_song, width=30).grid(row=0, column=1, padx=(6,0))

        ttk.Label(frm_search, text='原唱（可空白）').grid(row=1, column=0, sticky='w', pady=(4,0))
        self.var_orig_search = tk.StringVar()
        ttk.Entry(frm_search, textvariable=self.var_orig_search, width=30).grid(row=1, column=1, padx=(6,0), pady=(4,0))

        ttk.Button(frm_search, text='🔍 搜尋', command=self._search).grid(row=2, column=0, columnspan=2, pady=(8,0))

        # ── 搜尋結果 ──
        frm_result = ttk.LabelFrame(self, text='搜尋結果（點選後下載）', padding=8)
        frm_result.grid(row=1, column=0, sticky='ew', **pad)

        self.listbox = tk.Listbox(frm_result, height=6, width=60, activestyle='dotbox')
        self.listbox.pack(side='left', fill='both')
        sb = ttk.Scrollbar(frm_result, orient='vertical', command=self.listbox.yview)
        sb.pack(side='right', fill='y')
        self.listbox.config(yscrollcommand=sb.set)

        # ── 輸出設定 ──
        frm_out = ttk.LabelFrame(self, text='輸出設定', padding=8)
        frm_out.grid(row=2, column=0, sticky='ew', **pad)

        ttk.Label(frm_out, text='翻唱者名稱').grid(row=0, column=0, sticky='w')
        self.var_cover = tk.StringVar(value=self.cfg.get('cover_artist', ''))
        ttk.Entry(frm_out, textvariable=self.var_cover, width=20).grid(row=0, column=1, padx=(6,0))

        ttk.Label(frm_out, text='原唱名稱（SRT 替換）').grid(row=1, column=0, sticky='w', pady=(4,0))
        self.var_orig_replace = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self.var_orig_replace, width=20).grid(row=1, column=1, padx=(6,0), pady=(4,0))
        ttk.Label(frm_out, text='若歌詞裡有原唱名字，會自動替換', foreground='gray').grid(row=1, column=2, padx=6)

        ttk.Label(frm_out, text='輸出資料夾').grid(row=2, column=0, sticky='w', pady=(4,0))
        self.var_outdir = tk.StringVar(value=self.cfg.get('out_dir', str(OUT_DIR)))
        ttk.Entry(frm_out, textvariable=self.var_outdir, width=35).grid(row=2, column=1, padx=(6,0), pady=(4,0))
        ttk.Button(frm_out, text='…', width=3, command=self._pick_dir).grid(row=2, column=2, padx=4, pady=(4,0))

        # ── 下載按鈕 ──
        ttk.Button(self, text='⬇ 下載並轉換 SRT', command=self._download).grid(row=3, column=0, pady=8)

        # ── 狀態列 ──
        self.var_status = tk.StringVar(value='請輸入歌名後按搜尋')
        ttk.Label(self, textvariable=self.var_status, foreground='#555').grid(row=4, column=0, pady=(0,10))

    def _status(self, msg: str, color='#555'):
        self.var_status.set(msg)
        self.nametowidget('.').update_idletasks()

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_outdir.get())
        if d:
            self.var_outdir.set(d)

    def _search(self):
        song = self.var_song.get().strip()
        if not song:
            messagebox.showwarning('提示', '請輸入歌名')
            return
        self._status('搜尋中…')
        self.listbox.delete(0, 'end')
        threading.Thread(target=self._do_search, args=(song, self.var_orig_search.get().strip()), daemon=True).start()

    def _do_search(self, song, artist):
        try:
            self.results = search_lrclib(song, artist)
            self.after(0, self._fill_results)
        except Exception as e:
            self.after(0, lambda: self._status(f'搜尋失敗：{e}', 'red'))

    def _fill_results(self):
        self.listbox.delete(0, 'end')
        if not self.results:
            self._status('找不到有時間軸的歌詞，試試修改歌名或原唱')
            return
        for r in self.results:
            dur = r.get('duration', 0)
            m, s = divmod(int(dur or 0), 60)
            self.listbox.insert('end', f"{r.get('trackName','')} — {r.get('artistName','')}  [{m}:{s:02d}]")
        self._status(f'找到 {len(self.results)} 筆，點選後按下載')

    def _download(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning('提示', '請先從列表點選一首歌')
            return
        cover = self.var_cover.get().strip()
        if not cover:
            messagebox.showwarning('提示', '請填入翻唱者名稱')
            return
        idx = sel[0]
        item = self.results[idx]
        self._status('下載中…')
        threading.Thread(target=self._do_download, args=(item, cover), daemon=True).start()

    def _do_download(self, item: dict, cover: str):
        try:
            lrc = item.get('syncedLyrics') or get_synced_lyrics(item['id'])
            if not lrc:
                self.after(0, lambda: self._status('這首歌沒有時間軸歌詞', 'red'))
                return

            orig_replace = self.var_orig_replace.get().strip()
            srt = lrc_to_srt(lrc, cover, orig_replace)

            out_dir = Path(self.var_outdir.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', item.get('trackName', 'output'))
            out_path = out_dir / f'{safe_name}.srt'
            out_path.write_text(srt, encoding='utf-8-sig')  # UTF-8 BOM，剪映相容

            self.after(0, lambda: self._status(f'✅ 已儲存：{out_path.name}', '#090'))
            self._save_cfg()
        except Exception as e:
            self.after(0, lambda: self._status(f'下載失敗：{e}', 'red'))

    def _save_cfg(self):
        self.cfg['cover_artist'] = self.var_cover.get().strip()
        self.cfg['out_dir'] = self.var_outdir.get().strip()
        save_cfg(self.cfg)

    def _on_close(self):
        self._save_cfg()
        self.destroy()

if __name__ == '__main__':
    app = App()
    app.mainloop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 翻唱歌詞工具 — 搜尋歌詞、轉 SRT、簡轉繁、換歌手名"""

import re
import json
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import requests
import opencc
import syncedlyrics

BASE_DIR  = Path(__file__).parent.parent
OUT_DIR   = BASE_DIR / 'output'
CFG_FILE  = BASE_DIR / 'config.json'
LRCLIB    = 'https://lrclib.net/api'
HEADERS   = {'User-Agent': 'LyricTool/1.0'}

QQ_SEARCH = 'https://c.y.qq.com/soso/fcgi-bin/search_for_qq_cp'
QQ_LYRIC  = 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg'
QQ_HDR    = {
    'Referer': 'https://y.qq.com/',
    'Origin': 'https://y.qq.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
}

converter = opencc.OpenCC('s2twp')

# ── 設定 ──────────────────────────────────────────────────────
def load_cfg() -> dict:
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text('utf-8'))
        except Exception:
            pass
    return {}

def save_cfg(cfg: dict):
    CFG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), 'utf-8')

# ── LRC → SRT ─────────────────────────────────────────────────
def lrc_time_to_ms(ts: str) -> int:
    m = re.match(r'(\d+):(\d+)[.:](\d+)', ts)
    if not m:
        return 0
    mm, ss, cs = int(m.group(1)), int(m.group(2)), int(m.group(3))
    ms = cs * 10 if len(m.group(3)) == 2 else cs
    return mm * 60000 + ss * 1000 + ms

def ms_to_srt(ms: int) -> str:
    h  = ms // 3600000; ms %= 3600000
    m  = ms // 60000;   ms %= 60000
    s  = ms // 1000;    ms %= 1000
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def lrc_to_srt(lrc: str, cover_artist: str, orig_artist: str) -> str:
    lines = []
    for line in lrc.splitlines():
        m = re.match(r'\[(\d+:\d+[.:]\d+)\](.*)', line)
        if m:
            lines.append((lrc_time_to_ms(m.group(1)), m.group(2).strip()))
    if not lines:
        return ''
    srt_parts = []
    for i, (start_ms, text) in enumerate(lines):
        end_ms = lines[i + 1][0] if i + 1 < len(lines) else start_ms + 3000
        text_tw = converter.convert(text)
        if orig_artist and orig_artist in text_tw:
            text_tw = text_tw.replace(orig_artist, cover_artist)
        if text_tw:
            srt_parts.append(
                f'{len(srt_parts)+1}\n'
                f'{ms_to_srt(start_ms)} --> {ms_to_srt(end_ms)}\n'
                f'{text_tw}'
            )
    return '\n\n'.join(srt_parts)

# ── 搜尋（LRCLIB → QQ → NetEase → Musixmatch） ──────────────────
def search_lrclib(song: str, artist: str) -> list[dict]:
    q = f'{artist} {song}'.strip() if artist else song
    r = requests.get(f'{LRCLIB}/search', params={'q': q}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return [x for x in r.json() if x.get('syncedLyrics')]

def search_qq(song: str, artist: str) -> list[dict]:
    q = f'{song} {artist}'.strip() if artist else song
    r = requests.get(QQ_SEARCH, params={
        'w': q, 'p': 1, 'n': 10, 'format': 'json', 'cr': 1, 'g_tk': 5381, 't': 0,
    }, headers=QQ_HDR, timeout=10)
    r.raise_for_status()
    songs = r.json().get('data', {}).get('song', {}).get('list', [])
    results = []
    for s in songs:
        results.append({
            'trackName': s.get('songname', ''),
            'artistName': '、'.join(si['name'] for si in s.get('singer', [])),
            'albumName': s.get('albumname', ''),
            'duration': s.get('interval', 0),
            '_songmid': s.get('songmid', ''),
            '_source': 'QQ',
        })
    return results

def fetch_qq_lyric(songmid: str) -> str:
    r = requests.get(QQ_LYRIC, params={
        'songmid': songmid, 'format': 'json', 'nobase64': 1,
    }, headers=QQ_HDR, timeout=10)
    r.raise_for_status()
    return r.json().get('lyric', '')

# ── QQ 製作人員字幕清除 ────────────────────────────────────────
_CREDIT_RE = re.compile(
    r'^(編曲|编曲|Arrangement|製作人|制作人|Producer|'
    r'吉他|Guitar|鋼琴|Piano|貝斯|Bass|'
    r'音樂製作|音乐制作|Music\s*[Pp]roduction|'
    r'錄音師?|录音师?|Recording|錄音棚|录音棚|'
    r'和聲|和声|Backing\s*[Vv]ocal|'
    r'混音|Mixing|母帶|母带|Mastering|'
    r'藝人|艺人|製作統|制作统|監製|监制|'
    r'出品|發行|发行|營銷|营销|推廣|推广|'
    r'版權|版权|Rap[：:]|弦樂|弦乐|OP[：:]|SP[：:])'
)
_COPYRIGHT_RE = re.compile(r'著作權|著作权|翻唱翻錄|翻唱翻录|\(未經|\(未经')
_CI_RE        = re.compile(r'^(詞|词|曲|作詞|作词|作曲|填詞|填词)[：:]\s*(.+)$')

def _filter_qq_credits(lrc: str) -> str:
    parsed = []
    for line in lrc.splitlines():
        m = re.match(r'(\[\d+:\d+[.:]\d+\])(.*)', line)
        if m:
            parsed.append((m.group(1), m.group(2).strip()))

    詞_ts, 詞_p = None, None
    曲_ts, 曲_p = None, None
    output = []

    for ts, text in parsed:
        m_ci = _CI_RE.match(text)
        if m_ci:
            role, person = m_ci.group(1), m_ci.group(2).strip()
            if role in ('詞', '词', '作詞', '作词', '填詞', '填词') and not 詞_ts:
                詞_ts, 詞_p = ts, person
            elif role in ('曲', '作曲') and not 曲_ts:
                曲_ts, 曲_p = ts, person
            continue
        if _CREDIT_RE.match(text) or _COPYRIGHT_RE.search(text):
            continue
        output.append((ts, text))

    # 建立詞曲行（同人合併）
    ci_out = []
    if 詞_p and 曲_p and 詞_p == 曲_p:
        ci_out.append((詞_ts, f'詞曲：{詞_p}'))
    else:
        if 詞_p:
            ci_out.append((詞_ts, f'詞：{詞_p}'))
        if 曲_p:
            ci_out.append((曲_ts, f'曲：{曲_p}'))

    # 依時間戳排序合併回去
    all_items = output + ci_out
    all_items.sort(key=lambda x: lrc_time_to_ms(x[0][1:-1]))
    return '\n'.join(f'{ts}{text}' for ts, text in all_items)

def search_syncedlyrics(song: str, artist: str) -> list[dict]:
    q = f'{song} {artist}'.strip() if artist else song
    results = []
    for provider in ['NetEase', 'Musixmatch']:
        try:
            lrc = syncedlyrics.search(q, synced_only=True, providers=[provider])
            if lrc:
                results.append({
                    'trackName': song, 'artistName': artist or '',
                    'albumName': '', 'duration': 0,
                    'syncedLyrics': lrc, '_source': provider,
                })
        except Exception:
            pass
    return results

def search_all(song: str, artist: str) -> list[dict]:
    results = search_lrclib(song, artist)
    if not results:
        results = search_qq(song, artist)
    if not results:
        results = search_syncedlyrics(song, artist)
    return results

# ── GUI ───────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('AI 翻唱歌詞工具')
        self.resizable(False, False)
        self.cfg = load_cfg()
        self._results: list[dict] = []
        self._build()
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build(self):
        pad = dict(padx=10)

        # ── 搜尋區 ──
        frm = ttk.LabelFrame(self, text='搜尋歌詞', padding=8)
        frm.grid(row=0, column=0, sticky='ew', pady=(10, 4), **pad)

        ttk.Label(frm, text='歌名').grid(row=0, column=0, sticky='w')
        self.v_song = tk.StringVar()
        ttk.Entry(frm, textvariable=self.v_song, width=32).grid(row=0, column=1, padx=(6,0))

        ttk.Label(frm, text='原唱（選填）').grid(row=1, column=0, sticky='w', pady=(4,0))
        self.v_artist = tk.StringVar()
        ttk.Entry(frm, textvariable=self.v_artist, width=32).grid(row=1, column=1, padx=(6,0), pady=(4,0))

        ttk.Button(frm, text='🔍 搜尋', command=self._search).grid(row=2, column=0, columnspan=2, pady=(8,0))

        # ── 結果列表 ──
        frm2 = ttk.LabelFrame(self, text='搜尋結果（點選後下載）', padding=8)
        frm2.grid(row=1, column=0, sticky='ew', pady=4, **pad)

        self.listbox = tk.Listbox(frm2, height=7, width=62, activestyle='dotbox',
                                  selectmode='single')
        sb = ttk.Scrollbar(frm2, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side='left'); sb.pack(side='right', fill='y')

        # ── 輸出設定 ──
        frm3 = ttk.LabelFrame(self, text='輸出設定', padding=8)
        frm3.grid(row=2, column=0, sticky='ew', pady=4, **pad)

        ttk.Label(frm3, text='翻唱者名稱').grid(row=0, column=0, sticky='w')
        self.v_cover = tk.StringVar(value=self.cfg.get('cover_artist', ''))
        self._cb_cover = ttk.Combobox(frm3, textvariable=self.v_cover, width=21,
                                       values=self.cfg.get('cover_history', []))
        self._cb_cover.grid(row=0, column=1, padx=(6,0))

        ttk.Label(frm3, text='原唱名稱（替換用）').grid(row=1, column=0, sticky='w', pady=(4,0))
        self.v_replace = tk.StringVar()
        ttk.Entry(frm3, textvariable=self.v_replace, width=22).grid(row=1, column=1, padx=(6,0), pady=(4,0))
        ttk.Label(frm3, text='歌詞中出現時自動替換', foreground='gray').grid(row=1, column=2, padx=6)

        ttk.Label(frm3, text='輸出資料夾').grid(row=2, column=0, sticky='w', pady=(4,0))
        self.v_outdir = tk.StringVar(value=self.cfg.get('out_dir', str(OUT_DIR)))
        ttk.Entry(frm3, textvariable=self.v_outdir, width=36).grid(row=2, column=1, padx=(6,0), pady=(4,0))
        ttk.Button(frm3, text='…', width=3, command=self._pick_dir).grid(row=2, column=2, padx=4, pady=(4,0))

        # ── 按鈕 ──
        frm4 = ttk.Frame(self)
        frm4.grid(row=3, column=0, pady=6)
        ttk.Button(frm4, text='⬇ 下載並轉換 SRT', command=self._download).pack(side='left', padx=6)
        ttk.Button(frm4, text='📂 開啟輸出資料夾', command=self._open_dir).pack(side='left', padx=6)

        # ── 狀態 ──
        self.v_status = tk.StringVar(value='請輸入歌名後按搜尋')
        self._lbl_status = ttk.Label(self, textvariable=self.v_status, foreground='gray')
        self._lbl_status.grid(row=4, column=0, pady=(0,10))

    def _status(self, msg: str, color='gray'):
        self.v_status.set(msg)
        self._lbl_status.configure(foreground=color)
        self.update_idletasks()

    def _pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.v_outdir.get())
        if d:
            self.v_outdir.set(d)

    def _open_dir(self):
        subprocess.Popen(f'explorer "{Path(self.v_outdir.get())}"')

    def _search(self):
        song = self.v_song.get().strip()
        if not song:
            messagebox.showwarning('提示', '請填入歌名')
            return
        self.listbox.delete(0, 'end')
        self._status('搜尋中…')
        threading.Thread(target=self._do_search,
                         args=(song, self.v_artist.get().strip()), daemon=True).start()

    def _do_search(self, song, artist):
        try:
            self._results = search_all(song, artist)
            self.after(0, self._fill_list)
        except Exception as e:
            self.after(0, lambda: self._status(f'搜尋失敗：{e}', 'red'))

    def _fill_list(self):
        self.listbox.delete(0, 'end')
        if not self._results:
            self._status('找不到有時間軸的歌詞，試試修改歌名或原唱', 'orange')
            return
        for r in self._results[:10]:
            dur = r.get('duration', 0)
            m, s = divmod(int(dur or 0), 60)
            src = r.get('_source', 'LRCLIB')
            dur_str = f'[{m}:{s:02d}]' if dur else ''
            self.listbox.insert('end',
                f"  [{src}] {r.get('trackName','')}  —  {r.get('artistName','')}  {dur_str}")
        self._status(f'找到 {len(self._results)} 筆，點選後按下載', 'green')

    def _download(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning('提示', '請先從列表點選一首歌')
            return
        cover = self.v_cover.get().strip()
        if not cover:
            messagebox.showwarning('提示', '請填入翻唱者名稱')
            return
        item = self._results[sel[0]]
        self._status('轉換中…')
        threading.Thread(target=self._do_download,
                         args=(item, cover), daemon=True).start()

    def _do_download(self, item, cover):
        try:
            if item.get('_source') == 'QQ':
                lrc = _filter_qq_credits(fetch_qq_lyric(item['_songmid']))
            else:
                lrc = item.get('syncedLyrics', '')
            orig_r  = self.v_replace.get().strip()
            srt     = lrc_to_srt(lrc, cover, orig_r)
            out_dir = Path(self.v_outdir.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            safe    = re.sub(r'[\\/:*?"<>|]', '_', item.get('trackName', 'output'))
            path    = out_dir / f'{safe}.srt'
            path.write_text(srt, encoding='utf-8-sig')
            self.after(0, lambda: self._status(f'✅ 已儲存：{path.name}', 'green'))
            self.cfg['cover_artist'] = cover
            self.cfg['out_dir']      = self.v_outdir.get()
            history = self.cfg.get('cover_history', [])
            if cover not in history:
                history.insert(0, cover)
                self.cfg['cover_history'] = history[:20]
                self.after(0, lambda h=history[:20]: self._cb_cover.configure(values=h))
            save_cfg(self.cfg)
        except Exception as e:
            self.after(0, lambda: self._status(f'失敗：{e}', 'red'))

    def _on_close(self):
        self.cfg['cover_artist'] = self.v_cover.get().strip()
        self.cfg['out_dir']      = self.v_outdir.get().strip()
        save_cfg(self.cfg)
        self.destroy()

if __name__ == '__main__':
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    App().mainloop()

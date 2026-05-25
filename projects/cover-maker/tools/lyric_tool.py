#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 翻唱歌詞工具 — 搜尋歌詞、轉 SRT、簡轉繁、換歌手名"""

import re
import json
import threading
import subprocess
from pathlib import Path
from difflib import SequenceMatcher
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

NE_SEARCH = 'https://music.163.com/api/search/get/web'
NE_LYRIC  = 'https://music.163.com/api/song/lyric'
NE_HDR    = {
    'Referer': 'https://music.163.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
}

converter = opencc.OpenCC('s2twp')

def _is_cjk_dominant(text: str) -> bool:
    if not text:
        return False
    cjk = sum(1 for c in text if '一' <= c <= '鿿'
              or '぀' <= c <= 'ヿ'   # 日文假名
              or '가' <= c <= '힯')  # 韓文
    return cjk / len(text) > 0.35

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

def lrc_to_srt(lrc: str, cover_artist: str, orig_artist: str,
               translations: dict | None = None) -> str:
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
        is_credit_line = re.match(r'^(詞曲|詞|曲)[：:]', text_tw)
        if orig_artist and orig_artist in text_tw and not is_credit_line:
            text_tw = text_tw.replace(orig_artist, cover_artist)
        if translations and not is_credit_line:
            trans = translations.get(text, '')
            if trans:
                text_tw = f'{text_tw}\n{trans}'
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
# 明確關鍵字（行首即可，前面有前綴也能匹配）
_CREDIT_KW = re.compile(
    r'編曲|编曲|Arrangement|'
    r'製作人|制作人|Producer|'
    r'製作公司|制作公司|'
    r'混音|Mixing|'
    r'母帶|母带|Mastering|'
    r'錄音|录音|Recording|'
    r'和聲|和声|Backing|'
    r'吉他|Guitar|鋼琴|Piano|貝斯|Bass|鍵盤|Keyboard|鼓手|'
    r'弦樂|弦乐|音效|'
    r'藝人|艺人|統籌|统筹|監製|监制|'
    r'出品|發行|发行|營銷|营销|推廣|推广|宣傳|宣传|企劃|企划|'
    r'商務|商务|'
    r'版權|版权'
)
# 格式型：「短角色詞（不含歌詞字符）+ 冒號 + 內容」也視為製作資訊
_CREDIT_FMT = re.compile(r'^[^，。！？…\n]{2,20}[：:][^\n]{1,40}$')
_COPYRIGHT_RE = re.compile(r'著作權|著作权|翻唱翻錄|翻唱翻录|[（(]未[經经]|版權所有|版权所有|未經許可|未经许可')
_CI_RE        = re.compile(r'^(詞|词|曲|作詞|作词|作曲|填詞|填词)[：:]\s*(.+)$')

def _is_credit(text: str) -> bool:
    """判斷是否為製作人員字幕：關鍵字命中，或短角色+冒號格式且包含製作關鍵字。"""
    if _COPYRIGHT_RE.search(text):
        return True
    if re.match(r'^Rap[：:]|^OP[：:]|^SP[：:]', text):
        return True
    # 格式符合「角色：姓名」且角色部分含製作關鍵字
    if _CREDIT_FMT.match(text):
        role = text.split('：')[0].split(':')[0]
        if _CREDIT_KW.search(role):
            return True
    return False

def _ms_to_lrc(ms: int) -> str:
    m = ms // 60000; ms %= 60000
    s = ms // 1000;  ms %= 1000
    return f'[{m:02d}:{s:02d}.{ms // 10:02d}]'

def _get_ci_line(lrc: str) -> str:
    """從 LRC 中提取詞/曲資訊，回傳合併後的單行文字（如無則回傳空字串）。"""
    詞_p, 曲_p = None, None
    for line in lrc.splitlines():
        m = re.match(r'\[\d+:\d+[.:]\d+\](.*)', line)
        if not m:
            continue
        text = m.group(1).strip()
        mc = _CI_RE.match(text)
        if mc:
            role, person = mc.group(1), mc.group(2).strip()
            if role in ('詞', '词', '作詞', '作词', '填詞', '填词') and not 詞_p:
                詞_p = person
            elif role in ('曲', '作曲') and not 曲_p:
                曲_p = person
    if 詞_p and 曲_p:
        return f'詞曲：{詞_p}' if 詞_p == 曲_p else f'詞：{詞_p}　曲：{曲_p}'
    if 詞_p:
        return f'詞：{詞_p}'
    if 曲_p:
        return f'曲：{曲_p}'
    return ''

def _prepend_title(lrc: str, title: str, ci_line: str = '',
                   min_ms: int = 2000, max_ms: int = 10000) -> str:
    """在 LRC 開頭插入標題（和詞曲行），前奏 <2s 不插，>10s 只顯示到 10s。"""
    lines = [l for l in lrc.splitlines() if re.match(r'\[\d+:\d+[.:]\d+\]', l)]
    if not lines:
        return lrc
    m = re.match(r'\[(\d+:\d+[.:]\d+)\]', lines[0])
    if not m:
        return lrc
    first_ms = lrc_time_to_ms(m.group(1))
    if first_ms < min_ms:
        return lrc
    new = []
    if title:
        new.append(f'{_ms_to_lrc(0)}{title}')
    if ci_line:
        ci_ms = min(1000, first_ms // 2)
        new.append(f'{_ms_to_lrc(ci_ms)}{ci_line}')
    if first_ms > max_ms:
        new.append(_ms_to_lrc(max_ms))
    new.extend(lines)
    return '\n'.join(new)

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
        if _is_credit(text):
            continue
        output.append((ts, text))

    # 建立詞曲行（同人合併為「詞曲：」，不同人合成同一行）
    ci_out = []
    if 詞_p and 曲_p:
        if 詞_p == 曲_p:
            ci_out.append((詞_ts, f'詞曲：{詞_p}'))
        else:
            ci_out.append((詞_ts, f'詞：{詞_p}　曲：{曲_p}'))
    elif 詞_p:
        ci_out.append((詞_ts, f'詞：{詞_p}'))
    elif 曲_p:
        ci_out.append((曲_ts, f'曲：{曲_p}'))

    # 依時間戳排序合併回去
    all_items = output + ci_out
    all_items.sort(key=lambda x: lrc_time_to_ms(x[0][1:-1]))
    return '\n'.join(f'{ts}{text}' for ts, text in all_items)

def search_netease(song: str, artist: str) -> list[dict]:
    q = f'{song} {artist}'.strip() if artist else song
    r = requests.get(NE_SEARCH,
                     params={'s': q, 'type': 1, 'limit': 10, 'offset': 0},
                     headers=NE_HDR, timeout=10)
    r.raise_for_status()
    songs = r.json().get('result', {}).get('songs', [])
    results = []
    for s in songs:
        results.append({
            'trackName':  s.get('name', ''),
            'artistName': '、'.join(a['name'] for a in s.get('artists', [])),
            'albumName':  s.get('album', {}).get('name', ''),
            'duration':   s.get('duration', 0) // 1000,
            '_song_id':   s.get('id'),
            '_source':    'NetEase',
        })
    return results

def fetch_netease_lyric(song_id: int) -> str:
    r = requests.get(NE_LYRIC,
                     params={'id': song_id, 'lv': 1, 'kv': 1, 'tv': -1},
                     headers=NE_HDR, timeout=10)
    r.raise_for_status()
    return r.json().get('lrc', {}).get('lyric', '')

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

def _sim(a: str, b: str) -> float:
    """字串相似度 0~1，忽略大小寫與常見分隔符。"""
    if not a or not b:
        return 0.0
    norm = lambda s: re.sub(r'[\s\-_·・・]', '', s.lower())
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def _score(item: dict, song: str, artist: str) -> float:
    track_sim = _sim(item.get('trackName', ''), song)
    art_sim   = _sim(item.get('artistName', ''), artist) if artist else 0.0
    return track_sim * 0.7 + art_sim * 0.3

def search_all(song: str, artist: str) -> list[dict]:
    qq_res, lrclib_res, ne_res = [], [], []

    def _qq():
        try:
            nonlocal qq_res
            qq_res = search_qq(song, artist)
        except Exception:
            pass

    def _lrclib():
        try:
            nonlocal lrclib_res
            lrclib_res = search_lrclib(song, artist)
        except Exception:
            pass

    def _netease():
        try:
            nonlocal ne_res
            ne_res = search_netease(song, artist)
        except Exception:
            pass

    threads = [
        threading.Thread(target=_qq,       daemon=True),
        threading.Thread(target=_lrclib,   daemon=True),
        threading.Thread(target=_netease,  daemon=True),
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    results = qq_res + lrclib_res + ne_res
    if not results:
        results = search_syncedlyrics(song, artist)
    results.sort(key=lambda x: _score(x, song, artist), reverse=True)
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
        sb_y = ttk.Scrollbar(frm2, orient='vertical',   command=self.listbox.yview)
        sb_x = ttk.Scrollbar(frm2, orient='horizontal', command=self.listbox.xview)
        self.listbox.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        self.listbox.pack(side='left', fill='both', expand=True)

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

        self.v_bilingual = tk.BooleanVar(value=self.cfg.get('bilingual', False))
        ttk.Checkbutton(frm3, text='雙語字幕（加中文翻譯，限非中文歌曲）',
                        variable=self.v_bilingual).grid(row=3, column=0, columnspan=3,
                                                        sticky='w', pady=(6,0))

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
        for r in self._results:
            dur = r.get('duration', 0)
            m, s = divmod(int(dur or 0), 60)
            src     = r.get('_source', 'LRCLIB')
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
        item = self._results[sel[0]]
        self._status('轉換中…')
        threading.Thread(target=self._do_download,
                         args=(item, cover), daemon=True).start()

    def _do_download(self, item, cover):
        try:
            track   = item.get('trackName', '')
            orig_r  = self.v_replace.get().strip() or (item.get('artistName', '') if cover else '')
            source = item.get('_source', '')
            if source == 'QQ':
                lrc = _filter_qq_credits(fetch_qq_lyric(item['_songmid']))
                if cover:
                    lines = lrc.splitlines()
                    if lines:
                        m = re.match(r'(\[\d+:\d+[.:]\d+\])', lines[0])
                        if m:
                            lines[0] = f'{m.group(1)}{track} - {cover}'
                            lrc = '\n'.join(lines)
            elif source == 'NetEase':
                raw = fetch_netease_lyric(item['_song_id'])
                lrc = _filter_qq_credits(raw)
                ci_line = ''
                try:
                    qq_hits = search_qq(track, item.get('artistName', ''))
                    if qq_hits:
                        ci_line = _get_ci_line(fetch_qq_lyric(qq_hits[0]['_songmid']))
                except Exception:
                    pass
                lrc = _prepend_title(lrc, f'{track} - {cover}' if cover else '', ci_line)
            else:
                lrc = item.get('syncedLyrics', '')
                # 用歌名 + 歌手去 QQ 查詞曲（比同名比對更準）
                ci_line = ''
                try:
                    lrclib_artist = item.get('artistName', '')
                    qq_hits = search_qq(track, lrclib_artist)
                    if qq_hits:
                        ci_line = _get_ci_line(fetch_qq_lyric(qq_hits[0]['_songmid']))
                except Exception:
                    pass
                lrc = _prepend_title(lrc, f'{track} - {cover}' if cover else '', ci_line)
            # 雙語翻譯
            translations = {}
            if self.v_bilingual.get():
                self.after(0, lambda: self._status('翻譯中…'))
                lyric_texts = []
                for line in lrc.splitlines():
                    m = re.match(r'\[\d+:\d+[.:]\d+\](.*)', line)
                    if m:
                        t = m.group(1).strip()
                        if t and not _CI_RE.match(t) and not _is_cjk_dominant(t):
                            lyric_texts.append(t)
                if lyric_texts:
                    try:
                        from deep_translator import GoogleTranslator
                        translator = GoogleTranslator(source='auto', target='zh-TW')
                        chunk_size = 50
                        for i in range(0, len(lyric_texts), chunk_size):
                            chunk = lyric_texts[i:i + chunk_size]
                            results_t = translator.translate_batch(chunk)
                            for orig, trans in zip(chunk, results_t):
                                if trans and trans.strip() != orig.strip():
                                    translations[orig] = trans.strip()
                    except Exception as te:
                        self.after(0, lambda e=te: self._status(f'翻譯失敗：{e}', 'orange'))
            srt     = lrc_to_srt(lrc, cover, orig_r, translations or None)
            out_dir = Path(self.v_outdir.get())
            out_dir.mkdir(parents=True, exist_ok=True)
            safe    = re.sub(r'[\\/:*?"<>|]', '_', item.get('trackName', 'output'))
            path    = out_dir / f'{safe}.srt'
            path.write_text(srt, encoding='utf-8-sig')
            self.after(0, lambda: self._status(f'✅ 已儲存：{path.name}', 'green'))
            self.cfg['cover_artist'] = cover
            self.cfg['out_dir']      = self.v_outdir.get()
            self.cfg['bilingual']    = self.v_bilingual.get()
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

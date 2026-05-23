#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 翻唱歌詞工具 — 搜尋歌詞、轉 SRT、簡轉繁、換歌手名"""

import re
import json
import threading
from pathlib import Path

import requests
import opencc
import dearpygui.dearpygui as dpg

BASE_DIR  = Path(__file__).parent.parent
OUT_DIR   = BASE_DIR / 'output'
CFG_FILE  = BASE_DIR / 'config.json'
LRCLIB    = 'https://lrclib.net/api'
HEADERS   = {'User-Agent': 'LyricTool/1.0'}

converter = opencc.OpenCC('s2twp')
_results: list[dict] = []

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

# ── LRCLIB ────────────────────────────────────────────────────
def search_lrclib(song: str, artist: str) -> list[dict]:
    q = f'{artist} {song}'.strip() if artist else song
    r = requests.get(f'{LRCLIB}/search', params={'q': q}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return [x for x in r.json() if x.get('syncedLyrics')]

# ── UI 回呼 ───────────────────────────────────────────────────
def set_status(msg: str, color=(200, 200, 200)):
    dpg.set_value('status', msg)
    dpg.configure_item('status', color=color)

def do_search():
    global _results
    song   = dpg.get_value('inp_song').strip()
    artist = dpg.get_value('inp_artist').strip()
    if not song:
        set_status('請填入歌名', (255, 100, 100))
        return
    set_status('搜尋中…')
    dpg.configure_item('btn_search', enabled=False)

    def _run():
        global _results
        try:
            _results = search_lrclib(song, artist)
            dpg.delete_item('result_list', children_only=True)
            if not _results:
                set_status('找不到有時間軸的歌詞，試試修改歌名或原唱', (255, 180, 80))
            else:
                for r in _results[:10]:
                    dur = r.get('duration', 0)
                    m, s = divmod(int(dur or 0), 60)
                    label = f"{r.get('trackName','')}  —  {r.get('artistName','')}  [{m}:{s:02d}]"
                    dpg.add_selectable(label=label, parent='result_list',
                                       callback=lambda s, a, u: None)
                set_status(f'找到 {len(_results)} 筆，點選後按下載', (100, 220, 100))
        except Exception as e:
            set_status(f'搜尋失敗：{e}', (255, 100, 100))
        finally:
            dpg.configure_item('btn_search', enabled=True)

    threading.Thread(target=_run, daemon=True).start()

def do_download():
    # 找被選中的那一行
    selected = None
    for i, child in enumerate(dpg.get_item_children('result_list', 1)):
        if dpg.get_value(child):
            selected = i
            break
    if selected is None:
        set_status('請先點選一首歌', (255, 180, 80))
        return
    if selected >= len(_results):
        return
    item = _results[selected]

    cover   = dpg.get_value('inp_cover').strip()
    orig_r  = dpg.get_value('inp_orig_replace').strip()
    out_dir = dpg.get_value('inp_outdir').strip()

    if not cover:
        set_status('請填入翻唱者名稱', (255, 100, 100))
        return

    set_status('轉換中…')
    dpg.configure_item('btn_download', enabled=False)

    def _run():
        try:
            lrc  = item.get('syncedLyrics', '')
            srt  = lrc_to_srt(lrc, cover, orig_r)
            d    = Path(out_dir)
            d.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[\\/:*?"<>|]', '_', item.get('trackName', 'output'))
            path = d / f'{safe}.srt'
            path.write_text(srt, encoding='utf-8-sig')
            set_status(f'✅ 已儲存：{path}', (100, 220, 100))
            cfg = load_cfg()
            cfg['cover_artist'] = cover
            cfg['out_dir']      = out_dir
            save_cfg(cfg)
        except Exception as e:
            set_status(f'下載失敗：{e}', (255, 100, 100))
        finally:
            dpg.configure_item('btn_download', enabled=True)

    threading.Thread(target=_run, daemon=True).start()

def open_output():
    out = dpg.get_value('inp_outdir').strip()
    import subprocess
    subprocess.Popen(f'explorer "{Path(out)}"')

# ── 建立視窗 ──────────────────────────────────────────────────
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_cfg()

    dpg.create_context()
    dpg.create_viewport(title='AI 翻唱歌詞工具', width=620, height=540, resizable=False)
    dpg.setup_dearpygui()

    with dpg.font_registry():
        pass  # 使用系統預設字型

    with dpg.window(label='main', tag='main', no_title_bar=True, no_move=True,
                    no_resize=True, no_close=True):

        dpg.add_text('🔍  搜尋歌詞')
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text('歌名        ', color=(180, 180, 180))
            dpg.add_input_text(tag='inp_song', width=300, hint='例：月亮')
        with dpg.group(horizontal=True):
            dpg.add_text('原唱（選填）', color=(180, 180, 180))
            dpg.add_input_text(tag='inp_artist', width=200, hint='不填也可搜尋')
        dpg.add_button(label='搜尋', tag='btn_search', callback=do_search, width=80)

        dpg.add_spacer(height=8)
        dpg.add_text('📋  搜尋結果')
        dpg.add_separator()
        with dpg.child_window(tag='result_list', height=140, border=True):
            dpg.add_text('（搜尋後顯示結果）', color=(120, 120, 120))

        dpg.add_spacer(height=8)
        dpg.add_text('⚙️  輸出設定')
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_text('翻唱者名稱          ', color=(180, 180, 180))
            dpg.add_input_text(tag='inp_cover', width=200,
                               default_value=cfg.get('cover_artist', ''))
        with dpg.group(horizontal=True):
            dpg.add_text('原唱名稱（替換用）  ', color=(180, 180, 180))
            dpg.add_input_text(tag='inp_orig_replace', width=200,
                               hint='歌詞中若有出現會取代')
        with dpg.group(horizontal=True):
            dpg.add_text('輸出資料夾          ', color=(180, 180, 180))
            dpg.add_input_text(tag='inp_outdir', width=340,
                               default_value=cfg.get('out_dir', str(OUT_DIR)))

        dpg.add_spacer(height=8)
        with dpg.group(horizontal=True):
            dpg.add_button(label='⬇  下載並轉換 SRT', tag='btn_download',
                           callback=do_download, width=180)
            dpg.add_button(label='📂  開啟輸出資料夾',
                           callback=open_output, width=160)

        dpg.add_spacer(height=10)
        dpg.add_separator()
        dpg.add_text('請輸入歌名後按搜尋', tag='status', color=(200, 200, 200))

    dpg.set_primary_window('main', True)
    dpg.show_viewport()

    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

    dpg.destroy_context()

if __name__ == '__main__':
    main()

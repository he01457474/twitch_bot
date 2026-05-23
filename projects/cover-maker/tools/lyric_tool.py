#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 翻唱歌詞工具 — 搜尋歌詞、轉 SRT、簡轉繁、換歌手名"""

import re
import os
import sys
import json
from pathlib import Path
import requests
import opencc

BASE_DIR  = Path(__file__).parent.parent
OUT_DIR   = BASE_DIR / 'output'
CFG_FILE  = BASE_DIR / 'config.json'
LRCLIB    = 'https://lrclib.net/api'
HEADERS   = {'User-Agent': 'LyricTool/1.0 (AI Cover Maker)'}

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

# ── LRCLIB ────────────────────────────────────────────────────
def search_lrclib(song: str, artist: str) -> list[dict]:
    q = f'{artist} {song}'.strip() if artist else song
    r = requests.get(f'{LRCLIB}/search', params={'q': q}, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return [x for x in r.json() if x.get('syncedLyrics')]

# ── 主流程 ────────────────────────────────────────────────────
def ask(prompt: str, default: str = '') -> str:
    if default:
        val = input(f'{prompt} [{default}]: ').strip()
        return val if val else default
    return input(f'{prompt}: ').strip()

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_cfg()

    print('=' * 50)
    print('  AI 翻唱歌詞工具')
    print('=' * 50)

    while True:
        print()
        song   = ask('歌名')
        if not song:
            continue
        artist = ask('原唱（可直接 Enter 跳過）')

        print('\n搜尋中…')
        try:
            results = search_lrclib(song, artist)
        except Exception as e:
            print(f'搜尋失敗：{e}')
            continue

        if not results:
            print('找不到有時間軸的歌詞，試試修改歌名或原唱')
            continue

        print(f'\n找到 {len(results)} 筆結果：')
        for i, r in enumerate(results[:10], 1):
            dur = r.get('duration', 0)
            m, s = divmod(int(dur or 0), 60)
            print(f'  {i}. {r.get("trackName","")} — {r.get("artistName","")}  [{m}:{s:02d}]')

        sel = ask('\n選擇編號')
        if not sel.isdigit() or not (1 <= int(sel) <= len(results)):
            print('無效的選擇')
            continue
        item = results[int(sel) - 1]

        cover  = ask('翻唱者名稱', cfg.get('cover_artist', ''))
        orig_r = ask('原唱名稱（SRT 中若有出現會替換，可 Enter 跳過）')
        out_dir_str = ask('輸出資料夾', cfg.get('out_dir', str(OUT_DIR)))

        print('\n轉換中…')
        lrc = item.get('syncedLyrics', '')
        srt = lrc_to_srt(lrc, cover, orig_r)

        out_dir = Path(out_dir_str)
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', item.get('trackName', 'output'))
        out_path  = out_dir / f'{safe_name}.srt'
        out_path.write_text(srt, encoding='utf-8-sig')

        print(f'\n✅ 完成！檔案已儲存：{out_path}')

        cfg['cover_artist'] = cover
        cfg['out_dir']      = out_dir_str
        save_cfg(cfg)

        again = ask('\n繼續處理下一首？(y/n)', 'y')
        if again.lower() != 'y':
            break

    print('\n掰掰！')

if __name__ == '__main__':
    main()

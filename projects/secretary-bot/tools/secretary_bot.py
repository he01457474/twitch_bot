#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""私人秘書 Discord Bot — 待辦 + 台股追蹤 + 每日推送"""

import os
import re
import sqlite3
import asyncio
import logging
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import discord
from discord import app_commands
from discord.ext import tasks
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

# ── 基本設定 ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / '.env'
DB_FILE  = BASE_DIR / 'data' / 'secretary.db'
PID_FILE = Path(os.environ.get('TEMP', str(BASE_DIR))) / 'secretary_bot.pid'

load_dotenv(ENV_FILE)

DISCORD_TOKEN   = os.getenv('DISCORD_TOKEN', '')
GROQ_API_KEY    = os.getenv('GROQ_API_KEY', '')
FINMIND_TOKEN   = os.getenv('FINMIND_TOKEN', '')
PUSH_CHANNEL_ID = int(os.getenv('PUSH_CHANNEL_ID', '0') or '0')
# 若設定 MAIN_GUILD_ID，指令只在該伺服器生效；空白則全伺服器都開放
MAIN_GUILD_ID   = int(os.getenv('MAIN_GUILD_ID', '0') or '0')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('secretary')

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
GROQ_MODEL  = 'llama-3.3-70b-versatile'

FINMIND_BASE = 'https://api.finmindtrade.com/api/v4/data'
TWSE_BASE    = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY'
TPEX_DAILY_URLS = (
    'https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes',
    'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php',
)

# ── 術語字典 ──────────────────────────────────────────────────
TERMS: dict[str, str] = {
    'MA': '移動平均線，把一段時間的收盤價平均畫成一條線，用來判斷趨勢方向。',
    'KD': '隨機指標，80 以上代表超買可能要跌，20 以下代表超賣可能要漲。',
    'MACD': '趨勢指標，搭配紅綠柱狀圖判斷買賣時機。',
    'RSI': '相對強弱指數，超過 70 過熱、低於 30 過冷。',
    '布林通道': '均線加上下兩條軌道，碰上軌偏貴、碰下軌偏便宜。',
    '支撐': '股價跌到這個位置容易止跌，可以當買點參考。',
    '壓力': '股價漲到這個位置容易遇到賣壓，可以當賣點參考。',
    '突破': '股價向上穿越壓力位，通常是買進訊號。',
    '跌破': '股價向下穿越支撐位，通常是賣出訊號。',
    '缺口': '股價跳空開盤留下的空白區域，向上跳空通常是強勢訊號。',
    '量能': '成交量，量大代表市場熱度高。',
    '外資': '外國機構投資人，是影響台股最重要的力量之一。',
    '投信': '台灣本土基金公司，例如元大、富邦投信。',
    '自營商': '券商用自己的錢在股市買賣。',
    '三大法人': '外資、投信、自營商的合稱，他們的動向對股價影響很大。',
    '買超': '今天買進多於賣出，代表看好後市。',
    '賣超': '今天賣出多於買進，代表看空或獲利了結。',
    '融資': '向券商借錢買股票，屬於槓桿操作，風險較高。',
    '融券': '向券商借股票來賣（放空），之後再買回還給券商。',
    '主力': '資金龐大、能影響股價走勢的大戶。',
    '散戶': '一般個人投資人，資金相對小。',
    '本益比': '英文 PE，股價除以每股盈餘。越低可能越便宜，但也要看成長性。',
    'EPS': '每股盈餘，公司獲利除以股數，越高代表公司賺得越多。',
    '毛利率': '扣掉直接成本後的獲利比例，越高代表產品競爭力越強。',
    'ROE': '股東權益報酬率，代表公司用股東的錢賺了多少，15% 以上算優秀。',
    '殖利率': '股息除以股價，代表買股票每年能拿多少「利息」。',
    '除息': '扣掉現金股利的那天，股價通常下跌對應金額。',
    '配息': '公司把獲利以現金形式分給股東。',
    '法說會': '公司舉辦的法人說明會，常影響短期股價走勢。',
    '大盤': '整個股市的統稱，通常指台股加權指數。',
    '漲停': '當天最大漲幅限制（台股 10%）。',
    '跌停': '當天最大跌幅限制（台股 10%）。',
    '多頭': '看漲，預期股價上漲（多頭市場 = 牛市）。',
    '空頭': '看跌，預期股價下跌（空頭市場 = 熊市）。',
    '多空': '同時存在看漲和看跌力量，方向不明時常說「多空交戰」。',
    '盤整': '股價在一個區間震盪，沒有明顯漲跌趨勢。',
    '量縮': '成交量比前幾天少，代表市場觀望、動能不足。',
    '量增': '成交量比前幾天多，代表市場積極、動能增強。',
    'CoWoS': '台積電的先進封裝技術，把多個晶片緊密堆疊，AI 晶片大量採用。',
    'HBM': '高頻寬記憶體，AI 運算必備，由 SK Hynix、三星、美光生產。',
    'ODM': '幫客戶設計並生產產品，台灣電子廠的常見商業模式。',
    '晶圓代工': '幫客戶製造晶片，台積電是全球最大的晶圓代工廠。',
    '封測': '晶片封裝和測試，是半導體製造的最後一道工序。',
    'AI 伺服器': '專門用來跑 AI 運算的伺服器，比一般伺服器利潤高。',
    '低軌衛星': '在低軌道運行的衛星，延遲低速度快，Starlink 是代表。',
    '停損': '股價跌到預設位置就賣出，防止損失擴大。',
    '停利': '股價漲到預設位置就賣出，鎖定獲利。',
    '加碼': '在原有持股基礎上繼續買進，增加部位。',
    '減碼': '賣出部分持股，降低持倉比例。',
    '攤平': '股價跌後再買入拉低平均成本，風險是越攤越深。',
    '套牢': '股價跌破買進成本，帳面虧損無法賣出的狀態。',
    '解套': '原本套牢的股票漲回買進成本，可以損益兩平賣出。',
    '波段': '持股一段時間搭上一段漲勢再賣出，介於短線和長線之間。',
    '當沖': '當日沖銷，同一天內完成買進和賣出，不過夜。',
    '融資斷頭': '融資戶股票跌到一定程度，券商強制賣出，通常會加速股價下跌。',
    '軋空': '放空者被迫回補買股，造成股價急漲。',
    '換手率': '今天成交量占總股數的比例，越高代表交易越活絡。',
    '籌碼集中': '股票主要集中在少數大股東手中，通常代表大股東有信心持有。',
    '股價淨值比': '英文 PB，股價除以每股淨資產。小於 1 表示股價低於帳面價值。',
    '頭肩頂': 'K 線型態，出現後通常代表行情反轉向下。',
    'W 底': 'K 線型態，出現後通常代表行情反轉向上。',
    '儲能': '儲存電力的系統，搭配再生能源使用，相關台廠受惠。',
    '電動車': '電動汽車，帶動台灣電池、馬達、電控相關廠商需求。',
}

# ── 資料庫 ────────────────────────────────────────────────────
def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_FILE) as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS todos (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                done    INTEGER DEFAULT 0,
                created TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker  TEXT NOT NULL,
                name    TEXT,
                shares  INTEGER NOT NULL,
                cost    REAL NOT NULL,
                type    TEXT DEFAULT 'buy',
                created TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS learned_terms (
                term    TEXT PRIMARY KEY,
                learned TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS memories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kind        TEXT NOT NULL,
                content     TEXT NOT NULL,
                source_date TEXT NOT NULL,
                created     TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(kind, source_date)
            );
            CREATE INDEX IF NOT EXISTS idx_memories_kind_date
                ON memories(kind, source_date);
        ''')

def db():
    return sqlite3.connect(DB_FILE)

def get_cfg(key: str, default='') -> str:
    with db() as c:
        row = c.execute('SELECT value FROM config WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

def set_cfg(key: str, value: str):
    with db() as c:
        c.execute('INSERT OR REPLACE INTO config (key,value) VALUES (?,?)', (key, value))

_LOW_VALUE_MEMORY_PATTERNS = (
    '影響有限',
    '直接影響不大',
    '主要取決於本身的基本面',
    '主要取決於基本面',
    '市場供求',
)

def _clean_memory_text(content: str) -> str:
    lines = []
    for raw in (content or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(pattern in line for pattern in _LOW_VALUE_MEMORY_PATTERNS):
            continue
        lines.append(line)
    return '\n'.join(lines)

def remember(kind: str, content: str, source_date: str | None = None, keep: int = 80):
    content = _clean_memory_text(content)
    text = re.sub(r'\s+', ' ', content or '').strip()
    if not text:
        return
    text = text[:1200]
    source_date = source_date or datetime.date.today().isoformat()
    with db() as c:
        c.execute(
            'INSERT OR REPLACE INTO memories (kind, content, source_date) VALUES (?,?,?)',
            (kind, text, source_date),
        )
        c.execute(
            '''
            DELETE FROM memories
            WHERE id NOT IN (
                SELECT id FROM memories ORDER BY source_date DESC, id DESC LIMIT ?
            )
            ''',
            (keep,),
        )

def get_recent_memories(limit: int = 6, kind: str = '') -> list[str]:
    sql = 'SELECT source_date, kind, content FROM memories'
    params: tuple = ()
    if kind:
        sql += ' WHERE kind=?'
        params = (kind,)
    sql += ' ORDER BY source_date DESC, id DESC LIMIT ?'
    params = (*params, limit)
    with db() as c:
        rows = c.execute(sql, params).fetchall()
    return [f'{d} {k}：{content}' for d, k, content in rows]

_WEEKDAY_ALIASES = {
    '1': 0, '一': 0, '週一': 0, '星期一': 0, '禮拜一': 0, 'mon': 0, 'monday': 0,
    '2': 1, '二': 1, '週二': 1, '星期二': 1, '禮拜二': 1, 'tue': 1, 'tuesday': 1,
    '3': 2, '三': 2, '週三': 2, '星期三': 2, '禮拜三': 2, 'wed': 2, 'wednesday': 2,
    '4': 3, '四': 3, '週四': 3, '星期四': 3, '禮拜四': 3, 'thu': 3, 'thursday': 3,
    '5': 4, '五': 4, '週五': 4, '星期五': 4, '禮拜五': 4, 'fri': 4, 'friday': 4,
    '6': 5, '六': 5, '週六': 5, '星期六': 5, '禮拜六': 5, 'sat': 5, 'saturday': 5,
    '0': 6, '7': 6, '日': 6, '天': 6, '週日': 6, '週天': 6, '星期日': 6, '星期天': 6,
    '禮拜日': 6, '禮拜天': 6, 'sun': 6, 'sunday': 6,
}
_WEEKDAY_LABELS = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']

def _valid_hhmm(value: str) -> bool:
    if not re.match(r'^\d{2}:\d{2}$', value):
        return False
    h, m = map(int, value.split(':'))
    return 0 <= h <= 23 and 0 <= m <= 59

def _parse_weekday(value: str) -> int | None:
    key = value.strip().lower().replace(' ', '')
    return _WEEKDAY_ALIASES.get(key)

def _weekday_label(index: int) -> str:
    return _WEEKDAY_LABELS[index] if 0 <= index <= 6 else '週日'

# ── 股票名稱對照 ──────────────────────────────────────────────
_ticker_map: dict[str, str] = {}        # name → ticker
_ticker_map_ts: datetime.date | None = None
_stock_meta_map: dict[str, dict] = {}
_stock_meta_ts: datetime.date | None = None

_NAME_NORMALIZE = str.maketrans({
    '臺': '台',
})

def _stock_name_key(text: str) -> str:
    return re.sub(r'\s+', '', text.strip().translate(_NAME_NORMALIZE).upper())

def _stock_fuzzy_score(query: str, name: str) -> int | None:
    """名稱近似比對分數；數字越小越接近，None 表示不相近。"""
    q = _stock_name_key(query)
    n = _stock_name_key(name)
    if not q or not n:
        return None
    if q == n:
        return 0
    if len(q) >= 2 and n.startswith(q):
        return 3
    if len(q) >= 2 and q in n:
        return 4
    if len(q) >= 2 and len(q) == len(n) and sorted(q) == sorted(n):
        return 6
    if len(q) >= 2 and set(q).issubset(set(n)):
        return 7
    return None

def _load_stock_meta() -> dict[str, dict]:
    """從 FinMind 載入全市場股票基本資料，包含上市、上櫃、興櫃。"""
    global _stock_meta_map, _stock_meta_ts
    today = datetime.date.today()
    if _stock_meta_map and _stock_meta_ts == today:
        return _stock_meta_map

    meta: dict[str, dict] = {}
    try:
        r = requests.get(FINMIND_BASE, params={'dataset': 'TaiwanStockInfo'}, timeout=15)
        for item in r.json().get('data', []):
            code = str(item.get('stock_id') or '').strip()
            name = str(item.get('stock_name') or '').strip()
            if code and name:
                meta[code] = {
                    'ticker': code,
                    'name': name,
                    'industry_category': str(item.get('industry_category') or '').strip(),
                    'market_type': str(item.get('type') or '').strip(),
                }
    except Exception as e:
        log.warning(f'載入 FinMind 股票基本資料失敗: {e}')

    if meta:
        _stock_meta_map = meta
        _stock_meta_ts = today
    return _stock_meta_map

def _load_ticker_map() -> dict[str, str]:
    """載入「名稱→代號」對照表，每天快取一次；FinMind 可涵蓋上市、上櫃、興櫃。"""
    global _ticker_map, _ticker_map_ts
    today = datetime.date.today()
    if _ticker_map and _ticker_map_ts == today:
        return _ticker_map

    mapping: dict[str, str] = {}
    for code, item in _load_stock_meta().items():
        if item.get('name'):
            mapping[item['name']] = code

    sources = [
        'https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL',
        'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis',
    ]
    for url in sources:
        try:
            try:
                r = requests.get(url, timeout=10)
            except requests.exceptions.SSLError:
                requests.packages.urllib3.disable_warnings()
                r = requests.get(url, timeout=10, verify=False)
            for item in r.json():
                code = (item.get('Code') or item.get('SecuritiesCompanyCode') or '').strip()
                name = (item.get('Name') or item.get('CompanyName') or '').strip()
                if code and name:
                    mapping[name] = code
        except Exception as e:
            log.warning(f'載入股票清單失敗 {url}: {e}')

    if mapping:
        _ticker_map = mapping
        _ticker_map_ts = today
    return _ticker_map

def resolve_ticker(query: str) -> tuple[str, str] | tuple[None, None]:
    """
    輸入代號或名稱，回傳 (ticker, name)。
    找不到回傳 (None, None)。
    """
    query = query.strip()
    if not query:
        return None, None

    mapping = _load_ticker_map()
    holdings = get_holdings()

    # 代號走嚴格路徑：持股精準、官方精準；查不到就拒絕，避免 AI 拿裸代號亂編公司名稱。
    if re.fullmatch(r'[A-Za-z0-9]{4,6}', query):
        q = query.upper()
        for h in holdings:
            if h['ticker'].upper() == q:
                return h['ticker'], h['name']
        for name, code in mapping.items():
            if code.upper() == q:
                return code, name
        return None, None

    # 名稱先做精準比對，避免「台」這種短字直接抓到既有持股。
    for h in holdings:
        if query == h['name']:
            return h['ticker'], h['name']
    if query in mapping:
        return mapping[query], query

    # 部分名稱至少 2 個字，且只能命中一檔；多檔命中就要求使用者輸入更完整。
    if len(query) >= 2:
        official_matches = [(name, code) for name, code in mapping.items() if query in name]
        if len(official_matches) == 1:
            name, code = official_matches[0]
            return code, name

        holding_matches = [h for h in holdings if query in h['name']]
        if len(holding_matches) == 1:
            h = holding_matches[0]
            return h['ticker'], h['name']

        fuzzy_matches: dict[str, tuple[int, str, str]] = {}
        for h in holdings:
            score = _stock_fuzzy_score(query, h['name'])
            if score is not None:
                fuzzy_matches[h['ticker']] = (score, h['ticker'], h['name'])
        for name, code in mapping.items():
            score = _stock_fuzzy_score(query, name)
            if score is not None and (code not in fuzzy_matches or score < fuzzy_matches[code][0]):
                fuzzy_matches[code] = (score, code, name)
        ranked = sorted(fuzzy_matches.values(), key=lambda item: (item[0], len(item[2]), item[1]))
        if ranked and (len(ranked) == 1 or ranked[0][0] < ranked[1][0]):
            _, code, name = ranked[0]
            return code, name

    return None, None

def find_ticker_candidates(query: str, limit: int = 10) -> list[tuple[str, str]]:
    """回傳相近股票候選 [(ticker, name)]，給錯誤提示與 slash command autocomplete 使用。"""
    raw = query.strip()
    q = raw.upper()
    mapping = _load_ticker_map()
    holdings = get_holdings()

    candidates: dict[str, tuple[int, str, str]] = {}

    def add(code: str, name: str, score: int):
        if not code:
            return
        current = candidates.get(code)
        if current is None or score < current[0]:
            candidates[code] = (score, code, name or code)

    if not raw:
        for h in holdings[:limit]:
            add(h['ticker'], h['name'], 0)
        return [(code, name) for _, code, name in sorted(candidates.values())[:limit]]

    for h in holdings:
        code = h['ticker']
        name = h['name']
        code_u = code.upper()
        if code_u == q or name == raw:
            add(code, name, 0)
        elif len(q) >= 2 and code_u.startswith(q):
            add(code, name, 2)
        else:
            score = _stock_fuzzy_score(raw, name)
            if score is not None:
                add(code, name, score)

    for name, code in mapping.items():
        code_u = code.upper()
        if code_u == q or name == raw:
            add(code, name, 0)
        elif len(q) >= 2 and code_u.startswith(q):
            add(code, name, 2)
        else:
            score = _stock_fuzzy_score(raw, name)
            if score is not None:
                add(code, name, score)

    return [
        (code, name)
        for _, code, name in sorted(candidates.values(), key=lambda item: (item[0], len(item[2]), item[1]))[:limit]
    ]

def parse_shares(text: str) -> int | None:
    """解析股數輸入，支援「張」為單位（1 張 = 1000 股）；小數無條件捨去（不四捨五入），失敗回傳 None。"""
    text = text.strip().replace(',', '')
    m = re.match(r'^(\d+(?:\.\d+)?)\s*張$', text)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.match(r'^(\d+(?:\.\d+)?)\s*股?$', text)
    if m:
        return int(float(m.group(1)))
    return None

# 批次買賣解析：「股票名稱/代號」+「買入/賣出」+「股數」(+單位) (+價格)
# 例：昇達科賣出5股 2200.0 定穎投控賣出10股 187.0
_BATCH_TRADE_RE = re.compile(
    r'([^\s]+?)(買入|買進|加碼|賣出|賣掉|出清|減碼)'
    r'(\d+(?:\.\d+)?)\s*(張|股)?'
    r'(?:\s*(\d+(?:\.\d+)?))?'
)

# ── 股價 API ──────────────────────────────────────────────────
def _recent_trading_days(n=5) -> list[datetime.date]:
    days, d = [], datetime.date.today()
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= datetime.timedelta(days=1)
    return days

def _is_trading_hours() -> bool:
    """判斷現在是否為台股盤中（週一至五 09:00–13:30，台北時間）"""
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return datetime.time(9, 0) <= t <= datetime.time(13, 30)

def _num(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '').replace(' ', '')
    if not text or text in {'--', '---', '-', 'X', '除權息'}:
        return None
    text = text.replace('+', '')
    try:
        return float(text)
    except Exception:
        return None

def _roc_date(d: datetime.date) -> str:
    return f'{d.year - 1911}/{d.month:02d}/{d.day:02d}'

def _find_tpex_quote(payload, ticker: str) -> tuple[str, float] | None:
    rows: list = []
    headers: list[str] = []

    def collect(obj):
        nonlocal headers
        if isinstance(obj, list):
            if obj and all(isinstance(x, str) for x in obj) and any('收盤' in x for x in obj):
                headers = obj
            for item in obj:
                if isinstance(item, (list, dict)):
                    rows.append(item)
                    collect(item)
        elif isinstance(obj, dict):
            for key in ('fields', 'headers', 'columns'):
                val = obj.get(key)
                if isinstance(val, list) and any('收盤' in str(x) for x in val):
                    headers = [str(x) for x in val]
            for key in ('aaData', 'data', 'rows'):
                val = obj.get(key)
                if isinstance(val, list):
                    rows.extend(val)
            for val in obj.values():
                if isinstance(val, (list, dict)):
                    collect(val)

    collect(payload)

    for row in rows:
        if isinstance(row, dict):
            code = str(
                row.get('SecuritiesCompanyCode')
                or row.get('Code')
                or row.get('stock_id')
                or row.get('代號')
                or row.get('股票代號')
                or ''
            ).strip()
            if code != ticker:
                continue
            name = str(row.get('CompanyName') or row.get('Name') or row.get('stock_name') or row.get('名稱') or ticker).strip()
            for key in ('Close', 'close', 'ClosingPrice', '收盤', '收盤價'):
                close = _num(row.get(key))
                if close is not None:
                    return name or ticker, close
        elif isinstance(row, list) and row and str(row[0]).strip() == ticker:
            name = str(row[1]).strip() if len(row) > 1 else ticker
            close_index = None
            for i, header in enumerate(headers):
                if '收盤' in str(header):
                    close_index = i
                    break
            candidates = [close_index] if close_index is not None else [2, 3, 6]
            for idx in candidates:
                if idx is None or idx >= len(row):
                    continue
                close = _num(row[idx])
                if close is not None:
                    return name or ticker, close
    return None

def fetch_tpex_daily_price(ticker: str, trading_days: list[datetime.date]) -> dict | None:
    """TPEx 官方日成交備援；主要補上櫃/特殊交易狀態股票。"""
    day_quotes: list[tuple[datetime.date, str, float]] = []
    for d in trading_days:
        for url in TPEX_DAILY_URLS:
            params = {'response': 'json'}
            if 'www/zh-tw' in url:
                params.update({'date': d.strftime('%Y/%m/%d'), 'type': 'EW'})
            else:
                params.update({'l': 'zh-tw', 'd': _roc_date(d)})
            try:
                r = requests.get(url, params=params, headers=_HEADERS, timeout=10)
                quote = _find_tpex_quote(r.json(), ticker)
                if quote:
                    name, close = quote
                    day_quotes.append((d, name, close))
                    break
            except Exception:
                continue
        if len(day_quotes) >= 2:
            break
    if not day_quotes:
        return None
    today_close = day_quotes[0][2]
    yesterday_close = day_quotes[1][2] if len(day_quotes) > 1 else None
    return {
        'ticker': ticker,
        'name': day_quotes[0][1],
        'today_close': today_close,
        'yesterday_close': yesterday_close,
        'is_realtime': False,
        'source': 'tpex',
    }

def fetch_realtime_price(ticker: str) -> dict | None:
    """盤中即時報價，使用 yfinance（約 15 分鐘延遲）"""
    try:
        import yfinance as yf
        suffixes = ('.TW', '.TWO')
        meta = _load_stock_meta().get(ticker)
        if meta and meta.get('market_type') in ('tpex', 'emerging'):
            suffixes = ('.TWO', '.TW')
        for suffix in suffixes:
            try:
                yt = yf.Ticker(f'{ticker}{suffix}')
                fi = yt.fast_info
                cur  = getattr(fi, 'last_price', None)
                prev = getattr(fi, 'previous_close', None)
                if cur:
                    return {'ticker': ticker, 'name': ticker,
                            'today_close': cur, 'yesterday_close': prev,
                            'is_realtime': True}
            except Exception:
                continue
    except ImportError:
        log.warning('yfinance 未安裝，請執行安裝套件.bat')
    except Exception as e:
        log.warning(f'yfinance {ticker}: {e}')
    return None

def fetch_price(ticker: str) -> dict | None:
    """回傳 {ticker, name, today_close, yesterday_close, is_realtime}"""
    # 盤中優先走即時報價
    if _is_trading_hours():
        result = fetch_realtime_price(ticker)
        if result:
            return result

    trading_days = _recent_trading_days(5)
    today = trading_days[0]
    start = (trading_days[-1] - datetime.timedelta(days=3)).isoformat()

    if FINMIND_TOKEN:
        try:
            r = requests.get(FINMIND_BASE, params={
                'dataset': 'TaiwanStockPrice',
                'data_id': ticker,
                'start_date': start,
                'token': FINMIND_TOKEN,
            }, timeout=10)
            rows = r.json().get('data', [])
            if rows:
                rows.sort(key=lambda x: x['date'])
                name = rows[-1].get('stock_name', ticker)
                closes = {row['date']: row['close'] for row in rows}
                t = closes.get(today.isoformat())
                y = None
                for d in trading_days[1:]:
                    if d.isoformat() in closes:
                        y = closes[d.isoformat()]; break
                return {'ticker': ticker, 'name': name, 'today_close': t, 'yesterday_close': y, 'is_realtime': False}
        except Exception as e:
            log.warning(f'FinMind price {ticker}: {e}')

    # TWSE 備援
    try:
        ym = today.strftime('%Y%m01')
        r = requests.get(TWSE_BASE, params={'response': 'json', 'date': ym, 'stockNo': ticker}, timeout=10)
        j = r.json()
        rows = j.get('data', [])
        def parse_c(row):
            try: return float(row[6].replace(',', ''))
            except: return None
        closes = [(row[0], parse_c(row)) for row in rows if parse_c(row)]
        if len(closes) >= 2:
            title = j.get('title', '').split(' ')
            name = title[-1] if len(title) > 1 else ticker
            return {'ticker': ticker, 'name': name,
                    'today_close': closes[-1][1], 'yesterday_close': closes[-2][1], 'is_realtime': False}
    except Exception as e:
        log.warning(f'TWSE price {ticker}: {e}')

    result = fetch_tpex_daily_price(ticker, trading_days)
    if result:
        return result

    result = fetch_realtime_price(ticker)
    if result:
        return result
    return None

def fetch_recent_closes(ticker: str, days: int = 7) -> list[float]:
    """取最近幾個交易日收盤價，用於週報估算週漲跌。"""
    try:
        import yfinance as yf
        suffixes = ['.TW', '.TWO']
        meta = _load_stock_meta().get(ticker)
        if meta and meta.get('market_type') in ('tpex', 'emerging'):
            suffixes = ['.TWO', '.TW']
        for suffix in suffixes:
            try:
                hist = yf.Ticker(f'{ticker}{suffix}').history(period='10d', interval='1d')
                if hist is None or hist.empty or 'Close' not in hist:
                    continue
                closes = [float(v) for v in hist['Close'].dropna().tail(days).tolist()]
                if len(closes) >= 2:
                    return closes
            except Exception:
                continue
    except ImportError:
        log.warning('yfinance 未安裝，無法取得週報收盤資料')
    except Exception as e:
        log.warning(f'yfinance weekly closes {ticker}: {e}')
    return []

def fetch_institutional(ticker: str) -> dict | None:
    """回傳今日 {foreign, trust, dealer}（元），失敗回傳 None"""
    if not FINMIND_TOKEN:
        return None
    today = _recent_trading_days(1)[0]
    start = (today - datetime.timedelta(days=7)).isoformat()
    try:
        r = requests.get(FINMIND_BASE, params={
            'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
            'data_id': ticker,
            'start_date': start,
            'token': FINMIND_TOKEN,
        }, timeout=10)
        rows = [x for x in r.json().get('data', []) if x['date'] == today.isoformat()]
        result = {'foreign': 0, 'trust': 0, 'dealer': 0}
        for row in rows:
            net = (row.get('buy') or 0) - (row.get('sell') or 0)
            name = row.get('name', '')
            if '外資' in name:   result['foreign'] += net
            elif '投信' in name: result['trust']   += net
            elif '自營' in name: result['dealer']  += net
        return result
    except Exception as e:
        log.warning(f'FinMind institutional {ticker}: {e}')
        return None

def fetch_market_inst() -> dict:
    """大盤三大法人（外資/投信淨買超，元）"""
    if not FINMIND_TOKEN:
        return {}
    today = _recent_trading_days(1)[0]
    try:
        r = requests.get(FINMIND_BASE, params={
            'dataset': 'TaiwanStockInstitutionalInvestors',
            'start_date': today.isoformat(),
            'token': FINMIND_TOKEN,
        }, timeout=10)
        result = {}
        for row in r.json().get('data', []):
            if row.get('date') != today.isoformat(): continue
            result[row.get('name', '')] = (row.get('buy') or 0) - (row.get('sell') or 0)
        return result
    except Exception as e:
        log.warning(f'Market institutional: {e}')
        return {}

def fetch_stock_profile(ticker: str, display_name: str = '') -> dict:
    """補足個股基本資料，來源：FinMind 股票基本資料 + yfinance 公司摘要。"""
    profile = {
        'ticker': ticker,
        'name': display_name or ticker,
        'industry_category': '',
        'market_type': '',
        'english_name': '',
        'sector': '',
        'industry': '',
        'summary': '',
        'website': '',
    }
    meta = _load_stock_meta().get(ticker)
    if meta:
        profile.update({
            'name': meta.get('name') or profile['name'],
            'industry_category': meta.get('industry_category') or '',
            'market_type': meta.get('market_type') or '',
        })

    try:
        import yfinance as yf
        suffixes = ['.TW', '.TWO']
        if profile.get('market_type') in ('tpex', 'emerging'):
            suffixes = ['.TWO', '.TW']
        for suffix in suffixes:
            try:
                info = yf.Ticker(f'{ticker}{suffix}').info
            except Exception:
                continue
            if not info:
                continue
            profile.update({
                'english_name': info.get('longName') or info.get('shortName') or profile['english_name'],
                'sector': info.get('sector') or profile['sector'],
                'industry': info.get('industry') or profile['industry'],
                'summary': info.get('longBusinessSummary') or profile['summary'],
                'website': info.get('website') or profile['website'],
            })
            if profile['summary'] or profile['industry']:
                break
    except ImportError:
        log.warning('yfinance 未安裝，無法補足公司基本資料')
    except Exception as e:
        log.warning(f'yfinance profile {ticker}: {e}')

    return profile

# ── 持股計算 ──────────────────────────────────────────────────
def _is_etf(ticker: str) -> bool:
    """台灣 ETF 代號通常開頭為 0 或為 6 碼"""
    return ticker.startswith('0') or len(ticker) == 6

def get_holdings() -> list[dict]:
    with db() as c:
        rows = c.execute(
            'SELECT ticker,name,shares,cost,type FROM transactions ORDER BY created'
        ).fetchall()
    book: dict[str, dict] = {}
    for ticker, name, shares, cost, typ in rows:
        if ticker not in book:
            book[ticker] = {'ticker': ticker, 'name': name or ticker, 'shares': 0, 'total_cost': 0.0}
        h = book[ticker]
        if typ == 'buy':
            h['shares'] += shares
            h['total_cost'] += shares * cost
        elif typ == 'sell' and h['shares'] > 0:
            ratio = min(shares / h['shares'], 1.0)
            h['total_cost'] -= h['total_cost'] * ratio
            h['shares'] = max(0, h['shares'] - shares)
    return [
        {**h, 'avg_cost': h['total_cost'] / h['shares']}
        for h in book.values() if h['shares'] > 0
    ]

# ── 新聞爬蟲 ──────────────────────────────────────────────────
_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def scrape_stock_news(ticker: str, name: str, limit=2) -> list[str]:
    try:
        r = requests.get(
            f'https://api.cnyes.com/media/api/v1/newslist/category/TWS:{ticker}:STOCK'
            f'?limit={limit * 2}&page=1',
            headers=_HEADERS, timeout=8
        )
        items = r.json().get('data', {}).get('items', [])
        titles = [item['title'][:45] for item in items if item.get('title')][:limit]
        return titles
    except Exception:
        # 備援：爬 HTML
        try:
            r = requests.get(
                f'https://news.cnyes.com/news/cat/twstock?stock_id={ticker}',
                headers=_HEADERS, timeout=8
            )
            soup = BeautifulSoup(r.text, 'html.parser')
            titles = []
            for el in soup.find_all(['h3', 'h2', 'a'], limit=20):
                t = el.get_text(strip=True)
                if 10 < len(t) < 80 and t not in titles:
                    titles.append(t[:45])
                if len(titles) >= limit: break
            return titles
        except Exception:
            return []

def scrape_hot_themes() -> list[str]:
    try:
        r = requests.get(
            'https://api.cnyes.com/media/api/v1/newslist/category/tw_stock?limit=8&page=1',
            headers=_HEADERS, timeout=8
        )
        items = r.json().get('items', {}).get('data', [])
        titles = [item['title'][:50] for item in items if item.get('title')]
        if titles:
            return titles[:6]
    except Exception:
        pass
    # 備援：爬 HTML
    try:
        r = requests.get('https://news.cnyes.com/news/cat/tw_stock', headers=_HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, 'html.parser')
        seen, themes = set(), []
        for el in soup.find_all(['h3', 'h2'], limit=30):
            t = el.get_text(strip=True)
            if 5 < len(t) < 60 and t not in seen:
                themes.append(t[:50]); seen.add(t)
            if len(themes) >= 6: break
        return themes
    except Exception:
        return []

def scrape_intl_news(limit=10) -> list[str]:
    """爬國際股市/焦點新聞，作為大盤情勢背景（地緣政治、關稅、Fed利率、AI巨頭動向等），
    分類來源較容易隨 cnyes 調整，所以多抓幾類合併、互相備援。"""
    seen, titles = set(), []
    categories = (
        'headline',
        'wd_stock',
        'us_stock',
        'tw_macro',
        'forex',
        'commodity',
        'cn_stock',
    )
    for cat in categories:
        try:
            r = requests.get(
                f'https://api.cnyes.com/media/api/v1/newslist/category/{cat}?limit=10&page=1',
                headers=_HEADERS, timeout=8
            )
            for item in r.json().get('items', {}).get('data', []):
                t = (item.get('title') or '')[:50]
                if t and t not in seen:
                    seen.add(t)
                    titles.append(t)
        except Exception:
            continue
        if len(titles) >= limit:
            break
    return titles[:limit]

def _news_timestamp(item: dict) -> datetime.datetime | None:
    for key in ('publishAt', 'createdAt', 'updatedAt', 'newsTime', 'startAt'):
        value = item.get(key)
        if value is None:
            continue
        try:
            ts = int(value)
            if ts > 10_000_000_000:
                ts = ts // 1000
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            pass
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
            except Exception:
                continue
    return None

def _collect_cnyes_titles(category: str, days: int = 7, limit: int = 20, pages: int = 3) -> list[str]:
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    seen, titles, fallback = set(), [], []
    for page in range(1, pages + 1):
        try:
            r = requests.get(
                f'https://api.cnyes.com/media/api/v1/newslist/category/{category}?limit=20&page={page}',
                headers=_HEADERS,
                timeout=8,
            )
            items = r.json().get('items', {}).get('data', [])
            if not items:
                items = r.json().get('data', {}).get('items', [])
            for item in items:
                title = (item.get('title') or '').strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                ts = _news_timestamp(item)
                short = title[:70]
                if ts is None:
                    fallback.append(short)
                elif ts >= cutoff:
                    titles.append(short)
                if len(titles) >= limit:
                    return titles[:limit]
        except Exception:
            continue
    return (titles or fallback)[:limit]

def scrape_weekly_market_news(days: int = 7, limit: int = 35) -> list[str]:
    """固定抓最近一週市場新聞，給週報使用。"""
    categories = ('headline', 'wd_stock', 'us_stock', 'tw_macro', 'forex', 'commodity', 'cn_stock')
    seen, titles = set(), []
    per_cat = max(4, limit // len(categories) + 1)
    for cat in categories:
        for title in _collect_cnyes_titles(cat, days=days, limit=per_cat, pages=4):
            if title not in seen:
                seen.add(title)
                titles.append(title)
            if len(titles) >= limit:
                return titles[:limit]
    return titles[:limit]

def scrape_stock_weekly_news(ticker: str, name: str, days: int = 7, limit: int = 5) -> list[str]:
    titles = _collect_cnyes_titles(f'TWS:{ticker}:STOCK', days=days, limit=limit, pages=4)
    return titles or scrape_stock_news(ticker, name, limit=limit)

# ── Gemini ────────────────────────────────────────────────────
def ask_ai(prompt: str, max_tokens=800) -> str:
    if not groq_client:
        return '\uff08AI API \u672a\u8a2d\u5b9a\uff09'
    try:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {'role': 'system', 'content': '\u4f60\u662f\u53f0\u80a1\u6295\u8cc7\u52a9\u7406\uff0c\u53ea\u7528\u7e41\u9ad4\u4e2d\u6587\u56de\u8986\uff0c\u4e0d\u5f97\u6df7\u5165\u6cf0\u6587\u3001\u97d3\u6587\u3001\u65e5\u6587\u5047\u540d\u6216\u5176\u4ed6\u975e\u4e2d\u6587\u8a9e\u8a00\u3002\u63d0\u5230\u80a1\u7968\u6642\u4e00\u5f8b\u5beb\u6210\u300c\u516c\u53f8\u540d\u7a31(\u4ee3\u865f)\u300d\u683c\u5f0f\uff08\u4f8b\u5982\u53f0\u7a4d\u96fb(2330)\uff09\uff0c\u4e0d\u8981\u53ea\u5beb\u4ee3\u865f\u3002'},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.7,
        )
        text = resp.choices[0].message.content.strip()
        # \u6e05\u9664\u975e CJK/ASCII \u96dc\u5b57
        out = []
        for ch in text:
            cp = ord(ch)
            if 0x20 <= cp <= 0x7E:
                out.append(ch)
            elif cp in (9, 10, 13):  # tab, newline, cr
                out.append(ch)
            elif 0x4E00 <= cp <= 0x9FFF:
                out.append(ch)
            elif 0x3000 <= cp <= 0x303F:
                out.append(ch)
            elif 0xFF01 <= cp <= 0xFF60:
                out.append(ch)
            elif 0x2010 <= cp <= 0x2BFF:
                out.append(ch)
        return ''.join(out).strip()
    except Exception as e:
        log.warning(f'Groq: {e}')
        return '\uff08AI \u66ab\u6642\u7121\u6cd5\u4f7f\u7528\uff09'

def ai_holding_analysis(enriched: list[dict], insts: dict | None = None, market_context: str = '') -> str:
    if not enriched:
        return '目前沒有持股資料。'
    insts = insts or {}
    # 只分析個股，ETF 不需要逐檔分析
    stocks = [h for h in enriched if not _is_etf(h['ticker'])]
    etfs   = [h for h in enriched if _is_etf(h['ticker'])]

    def _line(h: dict) -> str:
        bits = [
            f"{h['name']}（{h['ticker']}）：股數{h['shares']:,}股，"
            f"均價{h['avg_cost']:.2f}元，現價{h.get('today_close') or '未知'}元"
        ]
        if h.get('day_pct') is not None:
            bits.append(f"今日{signed(h['day_pct'], '.2f')}%")
            if h['day_pct'] >= 9.5:
                bits.append('接近漲停')
            elif h['day_pct'] <= -9.5:
                bits.append('接近跌停')
        if h.get('pnl_pct') is not None:
            bits.append(f"目前損益{signed(h['pnl_pct'], '.1f')}%")
        inst = insts.get(h['ticker'])
        if inst and (inst.get('foreign') or inst.get('trust') or inst.get('dealer')):
            flow = []
            if inst.get('foreign'): flow.append(f"外資{signed(inst['foreign']/1e8, '.2f')}億")
            if inst.get('trust'):   flow.append(f"投信{signed(inst['trust']/1e8, '.2f')}億")
            if inst.get('dealer'):  flow.append(f"自營{signed(inst['dealer']/1e8, '.2f')}億")
            bits.append('、'.join(flow))
        return '，'.join(bits)

    summary = '\n'.join(_line(h) for h in stocks)
    etf_str = '、'.join(f"{h['name']}（{h['ticker']}）" for h in etfs) if etfs else ''
    # 這段只做總結與處置方向，逐檔明細已經在持股區塊顯示。
    word_limit = max(180, 35 * max(len(stocks), 3))
    prompt = (
        f"你是資深台股分析師，根據以下資料用繁體中文寫出今日持股摘要，總字數控制在 {word_limit} 字內，"
        f"不要寫沒有數據佐證的空泛敘述（例如「受惠產業成長」「基本面良好」「市場供需」「影響有限」這類套話），"
        f"不要重複說免責聲明。\n\n"
        + (f"近期市場情勢／題材參考：\n{market_context}\n\n" if market_context else '') +
        f"個股數據：\n{summary or '（無）'}\n"
        + (f"ETF（不需分析）：{etf_str}\n" if etf_str else '') +
        f"\n請按照以下格式輸出：\n\n"
        + ("【今日情勢】只寫 1-2 句有資訊量的判斷，每句都必須符合「來源市場/事件 → 受影響族群或股票 → 原因」格式，"
           "例如「美債殖利率上升 → 高本益比 AI 股承壓 → 折現率提高」或「美國雲端資本支出擴大 → 散熱/電力/PCB 族群受惠 → 伺服器建置需求增加」。"
           "必須點名是哪個市場、哪個新聞或哪個變數，並明確說受影響的是哪個族群或哪一檔持股。嚴禁寫「影響有限」「直接影響不大」"
           "「主要取決於基本面和市場供求」這類沒有操作價值的句子；如果資料不足以連結，"
           "就寫「今日新聞沒有明確可連結持股的事件，先看持股處置。」\n\n" if market_context else '') +
        f"【持股處置】用 2-4 點摘要即可，不要逐檔重複解讀。優先提到：部位股數較大、"
        f"接近漲停/跌停、法人買賣超明顯、損益幅度較大的股票。每點格式「・名稱（代號）：具體動作＋原因」，"
        f"原因必須引用具體數據或事件，例如股數、損益%、日漲跌%、外資/投信買賣超或上方市場事件，"
        f"動作可用續抱、觀察、分批停利、減碼、停損、等待回測等；資料不足就不要硬下結論。"
    )
    return ask_ai(prompt, max_tokens=min(1800, 200 + 60 * len(stocks)))

def ai_recommend_tickers(held_tickers: list[str], market_context: str = '') -> list[dict]:
    """請 AI 推薦股票代號，回傳 [{ticker, name, sector, trend_rel, reason, action}]"""
    exclude = '、'.join(held_tickers) if held_tickers else '無'
    raw = ask_ai(
        f"你是台股投資顧問，請用繁體中文推薦 2 檔值得觀察的台股，重點是貼近近期世界趨勢，"
        f"不一定要跟台積電或半導體供應鏈有關。\n\n"
        + (f"近期市場情勢／題材參考：\n{market_context}\n\n"
           f"請先從上述新聞找出可能影響台股的主題，再挑選跟主題合理相關的標的；"
           f"每個推薦都要說清楚「哪個市場/事件 → 哪個族群或股票 → 為什麼」。"
           f"如果某個題材跟台股沒有清楚連結，就不要硬扯。\n\n"
           if market_context else '') +
        f"排除以下已持有股票（代號）：{exclude}\n\n"
        f"推薦條件：\n"
        f"・兩檔盡量來自不同產業，不要都押同一個題材。\n"
        f"・可以考慮 AI 基建、電力/能源、軍工航太、網通、金融、原物料、消費、運輸等方向。\n"
        f"・不要為了推薦而推薦台積電；若沒有更好理由，避開市值最大、新聞最多的熱門股。\n\n"
        f"每一檔請嚴格按照以下格式輸出，不要加任何額外說明：\n"
        f"代號：XXXX\n"
        f"名稱：股票中文名稱\n"
        f"產業：例如電力、軍工航太、網通、金融、原物料、半導體設備、散熱等\n"
        f"趨勢關聯：用「來源市場/事件 → 受影響族群 → 原因」寫一句話\n"
        f"理由：一句話，必須具體到產業、產品、成本、訂單、利率、匯率或資金流，不要寫基本面良好\n"
        f"操作：一句話建議，必須包含觀察價位/分批/等待回測/停損條件其中之一\n\n"
        f"只輸出兩檔，每檔之間空一行，不要加股價。",
        max_tokens=400,
    )
    results = []
    for block in raw.strip().split('\n\n'):
        item = {}
        for line in block.strip().splitlines():
            for key, prefixes in [
                ('ticker',   ['代號：', '代號:']),
                ('name',     ['名稱：', '名稱:']),
                ('sector',   ['產業：', '產業:']),
                ('trend_rel', ['趨勢關聯：', '趨勢關聯:', '台積電關聯：', '台積電關聯:']),
                ('reason',   ['理由：', '理由:']),
                ('action',   ['操作：', '操作:']),
            ]:
                for prefix in prefixes:
                    if line.startswith(prefix):
                        item[key] = line[len(prefix):].strip()
                        break
        if 'ticker' in item and 'name' in item:
            results.append(item)
    return results

# ── 顏色工具 ──────────────────────────────────────────────────
def color(v: float) -> str:
    return '🔴' if v > 0 else ('🟢' if v < 0 else '🟡')

def arrow(v: float) -> str:
    return '📈' if v > 0 else ('📉' if v < 0 else '➡️')

def signed(v: float, fmt='.0f') -> str:
    return f'+{v:{fmt}}' if v >= 0 else f'{v:{fmt}}'

def _chunk_text(text: str, limit: int = 1024, sep: str = '\n\n') -> list[str]:
    """依分隔符把長文字切成多個不超過 limit 字數的區塊，
    用來把持股、法人、AI 分析等內容拆成多個 embed 欄位，避免超過 1024 字被截斷。"""
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    parts = text.split(sep)
    chunks, cur = [], ''
    for part in parts:
        candidate = part if not cur else f'{cur}{sep}{part}'
        if len(candidate) > limit and cur:
            chunks.append(cur)
            cur = part
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks

# ── 每日報告 ──────────────────────────────────────────────────
def build_report() -> discord.Embed:
    today = datetime.date.today()
    wd = ['一','二','三','四','五','六','日'][today.weekday()]
    date_str = f"{today.strftime('%Y/%m/%d')}（{wd}）"

    holdings = get_holdings()
    held_tickers = [h['ticker'] for h in holdings]
    non_etf = [h for h in holdings if not _is_etf(h['ticker'])][:4]

    # ── Phase 1：並行抓取所有網路資料 ──────────────────────────
    with ThreadPoolExecutor(max_workers=16) as ex:
        price_futs = {h['ticker']: ex.submit(fetch_price, h['ticker']) for h in holdings}
        inst_futs  = {h['ticker']: ex.submit(fetch_institutional, h['ticker']) for h in holdings}
        news_futs  = [(h, ex.submit(scrape_stock_news, h['ticker'], h['name'])) for h in non_etf]
        themes_fut = ex.submit(scrape_hot_themes)
        intl_fut   = ex.submit(scrape_intl_news)
        mkt_fut    = ex.submit(fetch_market_inst)

    prices = {t: f.result() for t, f in price_futs.items()}
    insts  = {t: f.result() for t, f in inst_futs.items()}
    news_results = [(h, f.result()) for h, f in news_futs]
    themes    = themes_fut.result()[:4]
    intl_news = intl_fut.result()
    mkt       = mkt_fut.result()

    # AI 用的市場情勢背景：國際情勢 + 台股焦點題材
    market_context_lines = []
    if intl_news:
        market_context_lines.append('國際情勢：' + '；'.join(intl_news[:5]))
    if themes:
        market_context_lines.append('台股焦點題材：' + '；'.join(themes))
    recent_memories = get_recent_memories(limit=5)
    if recent_memories:
        market_context_lines.append('秘書近期記憶：' + '；'.join(recent_memories))
    market_context = '\n'.join(market_context_lines)

    # 計算損益
    enriched, total_cost, total_value = [], 0.0, 0.0
    for h in holdings:
        p   = prices.get(h['ticker'])
        tc  = p['today_close']    if p else None
        yc  = p['yesterday_close'] if p else None
        avg, sh = h['avg_cost'], h['shares']

        cur = tc or yc  # 今日無收盤就用昨日收盤代替計算
        dc  = (tc - yc) if (tc and yc) else None
        dp  = dc / yc * 100 if (dc is not None and yc) else None
        pnl = (cur - avg) * sh if cur else None
        pp  = (cur - avg) / avg * 100 if cur else None

        total_cost  += avg * sh
        total_value += (cur * sh) if cur else (avg * sh)
        enriched.append({**h, 'today_close': tc, 'yesterday_close': yc,
                         'day_change': dc, 'day_pct': dp, 'pnl': pnl, 'pnl_pct': pp,
                         'is_realtime': p.get('is_realtime', False) if p else False})

    # ── Phase 2：並行 AI 運算 ────────────────────────────────
    with ThreadPoolExecutor(max_workers=6) as ex:
        ai_analysis_fut  = ex.submit(ai_holding_analysis, enriched, insts, market_context)
        ai_recommend_fut = ex.submit(ai_recommend_tickers, held_tickers, market_context)

    ai_text         = ai_analysis_fut.result()
    recommend_items = ai_recommend_fut.result()

    # 推薦股真實股價（並行）
    with ThreadPoolExecutor(max_workers=4) as ex:
        rec_futs = [(item, ex.submit(fetch_price, item['ticker'])) for item in recommend_items]

    recommend_lines = []
    for item, f in rec_futs:
        p = f.result()
        cur = (p.get('today_close') or p.get('yesterday_close')) if p else None
        if cur:
            if p and p.get('today_close'):
                label = '即時' if p.get('is_realtime') else '今收'
            else:
                label = '昨收'
            price_str = f'{label} {cur:.0f}元'
        else:
            price_str = '股價暫無資料'
        parts = [f"**{item.get('name', item['ticker'])} {item['ticker']}**（{price_str}）"]
        if item.get('sector'):
            parts.append(f"產業：{item['sector']}")
        if item.get('trend_rel'):
            parts.append(f"趨勢關聯：{item['trend_rel']}")
        parts.append(f"理由：{item.get('reason', '')}")
        parts.append(f"操作：{item.get('action', '')}")
        recommend_lines.append('\n'.join(parts))
    recommend_text = '\n\n'.join(recommend_lines)

    # ── 持股欄 ────────────────────────────────────────────────
    hold_parts = ['**今日持股**\n──────────']
    for e in enriched:
        tc, yc, dc, dp = e['today_close'], e['yesterday_close'], e['day_change'], e['day_pct']
        avg, pnl, pp = e['avg_cost'], e['pnl'], e['pnl_pct']
        is_rt = e.get('is_realtime', False)
        price_label = '即時' if is_rt else '今收'
        lines = [f'**{e["name"]} {e["ticker"]}**']
        lines.append(f'股數 {e["shares"]:,} 股')
        # 第一行：收盤價
        if tc and yc:
            lines.append(f'昨收 {yc:.0f} → {price_label} {tc:.0f}元 {arrow(dc) if dc else ""}')
        elif yc:
            lines.append(f'收盤 {yc:.0f}元（今日資料待更新）')
        # 第二行：日漲跌
        if dc is not None and dp is not None:
            limit_note = ''
            if dp >= 9.5:
                limit_note = '｜接近漲停'
            elif dp <= -9.5:
                limit_note = '｜接近跌停'
            lines.append(f'日漲跌 {signed(dc)}元（{signed(dp, ".2f")}%）{color(dc)}{limit_note}')
        # 第三行：成本對照（pnl/pp 已在 enriched 用 cur 算好）
        cur = tc or yc
        if cur is not None and pnl is not None:
            lines.append(f'成本 {avg:.2f} → 現價 {cur:.0f}元｜損益 {signed(pnl)}元（{signed(pp, ".1f")}%）{color(pnl)}')
        elif cur is not None:
            lines.append(f'成本 {avg:.2f} → 現價 {cur:.0f}元')
        else:
            lines.append(f'成本 {avg:.2f}元（尚無市價）')
        hold_parts.append('\n'.join(lines))

    any_realtime = any(e.get('is_realtime') for e in enriched)
    total_pnl = total_value - total_cost
    total_pct = total_pnl / total_cost * 100 if total_cost else 0
    rt_note = '（即時報價，約 15 分鐘延遲）' if any_realtime else ''
    hold_text = '\n\n'.join(hold_parts)
    hold_chunks = _chunk_text(hold_text)
    hold_summary = (
        f'投入 {total_cost/1e4:.1f}萬｜市值 {total_value/1e4:.2f}萬\n'
        f'總損益 {signed(total_pnl)}元 {color(total_pnl)}（{signed(total_pct, ".2f")}%）{rt_note}'
    )

    # ── 法人欄 ────────────────────────────────────────────────
    def fi(v):
        return f'{signed(v / 1e8, ".2f")}億 {color(v)}'

    inst_parts = ['**三大法人**\n──────────']
    has_inst_data = False
    for e in enriched:
        inst = insts.get(e['ticker'])
        if not inst:
            continue
        if inst['foreign'] == 0 and inst['trust'] == 0 and inst['dealer'] == 0:
            continue
        has_inst_data = True
        inst_parts.append(
            f'**{e["name"]} {e["ticker"]}**\n'
            f'外資 {fi(inst["foreign"])}\n'
            f'投信 {fi(inst["trust"])}\n'
            f'自營 {fi(inst["dealer"])}'
        )
    if mkt:
        fnet = sum(v for k, v in mkt.items() if '外資' in k)
        tnet = sum(v for k, v in mkt.items() if '投信' in k)
        inst_parts.append(
            f'──────────\n'
            f'大盤外資 {signed(fnet/1e8, ".0f")}億\n'
            f'大盤投信 {signed(tnet/1e8, ".0f")}億'
        )
    # 無個股資料且無大盤資料，整欄不顯示
    inst_text = '\n\n'.join(inst_parts) if (has_inst_data or mkt) else ''
    inst_chunks = _chunk_text(inst_text)

    # ── 新聞欄（無新聞的股票略過）────────────────────────────
    news_pairs: list[tuple[str, str]] = []
    for h, news in news_results:
        if news:
            news_pairs.append((f'{h["name"]} {h["ticker"]}', '\n'.join(f'・{n}' for n in news)))

    # ── 新手術語 ──────────────────────────────────────────────
    full = hold_text + inst_text + ' '.join(themes) + ' '.join(intl_news) + ai_text + recommend_text
    with db() as c:
        learned = {r[0] for r in c.execute('SELECT term FROM learned_terms').fetchall()}
    new_terms = [(t, e) for t, e in TERMS.items() if t not in learned and t in full][:3]
    if new_terms:
        with db() as c:
            c.executemany('INSERT OR IGNORE INTO learned_terms (term) VALUES (?)', [(t,) for t, _ in new_terms])
    term_text = '\n'.join(f'**{t}**：{e}' for t, e in new_terms)

    # ── 組 Embed ──────────────────────────────────────────────
    embed = discord.Embed(title=f'📊 每日市場報告｜{date_str}', color=0xE74C3C)

    for chunk in hold_chunks:
        embed.add_field(name='​', value=chunk, inline=False)
    embed.add_field(name='💰 總覽', value=hold_summary, inline=False)

    for chunk in inst_chunks:
        embed.add_field(name='​', value=chunk, inline=False)

    if news_pairs:
        embed.add_field(name='📰 持股新聞', value='​', inline=False)
        for i, (n, v) in enumerate(news_pairs):
            embed.add_field(name=n, value=v[:1024] or '​', inline=True)
            if i % 2 == 1:
                embed.add_field(name='​', value='​', inline=False)

    advice_text = ai_text
    if recommend_text:
        advice_text += '\n\n**💎 潛力股推薦**\n' + recommend_text
    for i, chunk in enumerate(_chunk_text(advice_text, sep='\n')):
        embed.add_field(name=('🤖 AI 參考建議' if i == 0 else '​'), value=chunk, inline=False)
    if term_text:
        embed.add_field(name='📖 今日新詞', value=term_text[:1024], inline=False)
    embed.set_footer(text='⚠️ 以上為 AI 輔助參考，不構成投資建議，請依自身判斷操作。')

    remember('daily_report', f'{ai_text}\n{recommend_text}', today.isoformat())
    return embed

def build_weekly_report() -> discord.Embed:
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=6)
    date_range = f"{week_start.strftime('%Y/%m/%d')} - {today.strftime('%Y/%m/%d')}"
    holdings = get_holdings()
    non_etf = [h for h in holdings if not _is_etf(h['ticker'])][:6]

    with ThreadPoolExecutor(max_workers=16) as ex:
        price_futs = {h['ticker']: ex.submit(fetch_price, h['ticker']) for h in holdings}
        close_futs = {h['ticker']: ex.submit(fetch_recent_closes, h['ticker'], 7) for h in holdings}
        inst_futs  = {h['ticker']: ex.submit(fetch_institutional, h['ticker']) for h in holdings}
        news_futs  = [(h, ex.submit(scrape_stock_weekly_news, h['ticker'], h['name'], 7, 5)) for h in non_etf]
        weekly_market_fut = ex.submit(scrape_weekly_market_news, 7, 35)
        mkt_fut    = ex.submit(fetch_market_inst)

    prices = {t: f.result() for t, f in price_futs.items()}
    closes = {t: f.result() for t, f in close_futs.items()}
    insts  = {t: f.result() for t, f in inst_futs.items()}
    news_results = [(h, f.result()) for h, f in news_futs]
    weekly_market_news = weekly_market_fut.result()[:35]
    mkt = mkt_fut.result()
    recent_memories = get_recent_memories(limit=8)

    holding_lines = []
    for h in holdings:
        ticker = h['ticker']
        p = prices.get(ticker) or {}
        recent = closes.get(ticker) or []
        cur = p.get('today_close') or p.get('yesterday_close') or (recent[-1] if recent else None)
        week_pct = None
        if len(recent) >= 2 and recent[0]:
            week_pct = (recent[-1] - recent[0]) / recent[0] * 100
        day_pct = None
        if p.get('today_close') and p.get('yesterday_close'):
            day_pct = (p['today_close'] - p['yesterday_close']) / p['yesterday_close'] * 100
        pnl_pct = (cur - h['avg_cost']) / h['avg_cost'] * 100 if cur else None
        inst = insts.get(ticker) or {}
        flow = []
        if inst.get('foreign'): flow.append(f"外資{signed(inst['foreign']/1e8, '.2f')}億")
        if inst.get('trust'): flow.append(f"投信{signed(inst['trust']/1e8, '.2f')}億")
        if inst.get('dealer'): flow.append(f"自營{signed(inst['dealer']/1e8, '.2f')}億")
        cur_str = f'{cur:.0f}' if cur else '未知'
        week_str = f'{signed(week_pct, ".2f")}%' if week_pct is not None else '缺資料'
        day_str = f'{signed(day_pct, ".2f")}%' if day_pct is not None else '缺資料'
        pnl_str = f'{signed(pnl_pct, ".1f")}%' if pnl_pct is not None else '缺資料'
        holding_lines.append(
            f"{h['name']}({ticker})：股數{h['shares']:,}股，均價{h['avg_cost']:.2f}，"
            f"現價{cur_str}，"
            f"近週{week_str}，"
            f"單日{day_str}，"
            f"持股損益{pnl_str}，"
            f"法人{'、'.join(flow) if flow else '無明顯資料'}"
        )

    news_lines = []
    for h, items in news_results:
        for item in items:
            news_lines.append(f"{h['name']}({h['ticker']})：{item}")
    market_lines = []
    if weekly_market_news:
        market_lines.append('最近 7 天市場新聞：' + '；'.join(weekly_market_news))
    if mkt:
        fnet = sum(v for k, v in mkt.items() if '外資' in k)
        tnet = sum(v for k, v in mkt.items() if '投信' in k)
        market_lines.append(f"最近一日大盤法人：外資{signed(fnet/1e8, '.0f')}億，投信{signed(tnet/1e8, '.0f')}億")
    if recent_memories:
        market_lines.append('秘書過去記憶：' + '；'.join(recent_memories))

    prompt = (
        f"你是台股週報分析師，請用繁體中文寫本週市場週報，總字數 500-700 字。"
        f"不要籠統說『市場震盪』『題材輪動』，每個判斷都要連到下面的持股數據、法人資料或新聞。"
        f"所有判斷都要寫出「來源市場/事件 → 受影響族群或股票 → 原因」，"
        f"例如美股科技股、美元、美債、油價、銅價、中國需求、地緣政治、AI 資本支出分別影響什麼。\n\n"
        f"週報區間：{date_range}。新聞資料固定抓最近 7 天，請用整週脈絡分析，不要只看最後一天。\n\n"
        f"持股數據：\n{chr(10).join(holding_lines) if holding_lines else '目前沒有持股'}\n\n"
        f"近期市場/世界趨勢：\n{chr(10).join(market_lines) if market_lines else '新聞資料不足'}\n\n"
        f"持股相關新聞：\n{chr(10).join(news_lines[:12]) if news_lines else '無明確持股新聞'}\n\n"
        f"請完全照下面格式輸出：\n\n"
        f"**📊 持股週績效**\n"
        f"用數字點出本週表現最好/最弱、部位較大的持股，資料不足就明說是以目前損益和近週資料判斷。\n\n"
        f"**🏦 三大法人與資金方向**\n"
        f"結合個股法人和大盤法人，說明資金偏向哪些族群，避免只列買超賣超；必須指出是外資或投信影響哪檔/哪個族群。\n\n"
        f"**📰 本週關鍵事件 TOP5**\n"
        f"條列 5 點，每點格式固定為「來源市場/事件 → 台股影響對象 → 原因」。\n\n"
        f"**🔮 下週觀察重點**\n"
        f"列 3 點，包含要觀察的題材、風險和持股操作方向。\n\n"
        f"**📖 新手學習提醒**\n"
        f"用一句話解釋一個本週內容用得到的台股術語。"
    )
    result = ask_ai(prompt, max_tokens=1400)
    embed = discord.Embed(
        title=f'📅 本週市場回顧｜{today.strftime("%Y/%m/%d")}',
        description=result[:4096],
        color=0x3498DB
    )
    embed.set_footer(text='⚠️ 以上為 AI 輔助分析，不構成投資建議。')
    remember('weekly_report', result, today.isoformat())
    return embed

# ── Bot ───────────────────────────────────────────────────────
intents = discord.Intents.default()
bot  = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

def _guild_allowed(guild_id: int) -> bool:
    """若未設定 MAIN_GUILD_ID，所有伺服器都允許；設定後只允許該伺服器。"""
    return (not MAIN_GUILD_ID) or (guild_id == MAIN_GUILD_ID)

async def _check_guild(interaction: discord.Interaction) -> bool:
    """指令入口守衛，不在允許的伺服器時靜默拒絕。"""
    if not _guild_allowed(interaction.guild_id or 0):
        await interaction.response.send_message('此伺服器未啟用私人秘書功能。', ephemeral=True)
        return False
    return True

@bot.event
async def on_ready():
    # 先同步到允許的伺服器
    for guild in bot.guilds:
        if not _guild_allowed(guild.id):
            log.info(f'跳過同步（非主伺服器）：{guild.name}')
            continue
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            log.info(f'指令已同步到伺服器：{guild.name}')
        except Exception as e:
            log.warning(f'伺服器 {guild.name} 同步失敗: {e}')

    # 清掉舊的全域指令
    tree.clear_commands(guild=None)
    await tree.sync()
    log.info(f'Bot 已上線：{bot.user}，共加入 {len(bot.guilds)} 個伺服器')
    if not daily_push.is_running():
        daily_push.start()
    if not weekly_push.is_running():
        weekly_push.start()

# ── 待辦指令 ──────────────────────────────────────────────────
@tree.command(name='待辦', description='待辦事項管理')
@app_commands.rename(action='動作', content='內容')
@app_commands.describe(action='選擇動作', content='新增時填內容，完成/刪除時填編號')
@app_commands.choices(action=[
    app_commands.Choice(name='新增', value='add'),
    app_commands.Choice(name='查看清單', value='list'),
    app_commands.Choice(name='標記完成', value='done'),
    app_commands.Choice(name='刪除', value='delete'),
])
async def cmd_todo(interaction: discord.Interaction, action: str, content: str = ''):
    if not await _check_guild(interaction): return
    a = action.lower().strip()
    if a == 'add':
        if not content:
            await interaction.response.send_message('用法：`/todo add 要做的事`', ephemeral=True); return
        with db() as c:
            c.execute('INSERT INTO todos (content) VALUES (?)', (content,))
        await interaction.response.send_message(f'✅ 已新增：{content}', ephemeral=True)

    elif a == 'list':
        with db() as c:
            rows = c.execute('SELECT id,content,done FROM todos ORDER BY id').fetchall()
        if not rows:
            await interaction.response.send_message('目前沒有待辦事項。', ephemeral=True); return
        lines = [f'{"✅" if done else "⬜"} `{id_}` {cont}' for id_, cont, done in rows]
        await interaction.response.send_message('\n'.join(lines), ephemeral=True)

    elif a == 'done':
        if not content.isdigit():
            await interaction.response.send_message('用法：`/todo done 1`', ephemeral=True); return
        with db() as c:
            c.execute('UPDATE todos SET done=1 WHERE id=?', (int(content),))
        await interaction.response.send_message(f'✅ 已完成 #{content}', ephemeral=True)

    elif a == 'delete':
        if not content.isdigit():
            await interaction.response.send_message('用法：`/todo delete 1`', ephemeral=True); return
        with db() as c:
            c.execute('DELETE FROM todos WHERE id=?', (int(content),))
        await interaction.response.send_message(f'🗑️ 已刪除 #{content}', ephemeral=True)
    else:
        await interaction.response.send_message('可用：`add` / `list` / `done` / `delete`', ephemeral=True)

def _best_name(rticker: str, rname: str | None, p: dict | None) -> str:
    """挑選最佳顯示名稱：優先用 resolve_ticker 解析到的中文名，
    避免 yfinance 查無公司名稱時，把代號本身當成佔位名稱存進資料庫。"""
    if rname and rname != rticker:
        return rname
    if p and p.get('name') and p['name'] != rticker:
        return p['name']
    return rname or rticker

async def _execute_trade(loop, rticker: str, rname: str, parsed_shares: int, price: float, typ: str):
    """批次買賣用：執行單筆買入/賣出並寫入資料庫，回傳 (是否成功, 一行摘要)。typ: 'buy' | 'sell'"""
    if typ == 'buy':
        p = await loop.run_in_executor(None, fetch_price, rticker)
        name = _best_name(rticker, rname, p)
        actual_price = price if price > 0 else ((p.get('today_close') or p.get('yesterday_close')) if p else None)
        if not actual_price:
            return False, f'❌ {rname or rticker}({rticker})：查不到目前市價，請補上價格'
        with db() as c:
            c.execute('INSERT INTO transactions (ticker,name,shares,cost,type) VALUES (?,?,?,?,?)',
                      (rticker, name, parsed_shares, actual_price, 'buy'))
        note = '（市價）' if price <= 0 else ''
        return True, f'✅ 買入 **{name}({rticker})** × {parsed_shares:,}股 @ {actual_price:,.0f}元{note}'
    else:
        hs = get_holdings()
        h = next((x for x in hs if x['ticker'] == rticker), None)
        if not h or h['shares'] < parsed_shares:
            disp_name = h['name'] if h else (rname or rticker)
            return False, f'❌ {disp_name}({rticker})：持股不足（目前 {h["shares"] if h else 0} 股）'
        actual_price = price
        if actual_price <= 0:
            p = await loop.run_in_executor(None, fetch_price, rticker)
            actual_price = (p.get('today_close') or p.get('yesterday_close')) if p else None
        if not actual_price:
            return False, f'❌ {h["name"]}({rticker})：查不到目前市價，請補上價格'
        realized = (actual_price - h['avg_cost']) * parsed_shares
        with db() as c:
            c.execute('INSERT INTO transactions (ticker,name,shares,cost,type) VALUES (?,?,?,?,?)',
                      (rticker, h['name'], parsed_shares, actual_price, 'sell'))
        note = '（市價）' if price <= 0 else ''
        return True, (f'✅ 賣出 **{h["name"]}({rticker})** × {parsed_shares:,}股 @ {actual_price:,.0f}元{note}'
                      f'｜損益 {signed(realized)}元 {color(realized)}')

# ── 股票指令 ──────────────────────────────────────────────────
@tree.command(name='股票', description='股票買賣記錄與損益查詢')
@app_commands.rename(action='動作', ticker='股票', shares='股數', price='價格', batch='批次輸入')
@app_commands.describe(
    action='選擇動作',
    ticker='股票代號或名稱（例如 2330 或 台積電）',
    shares='股數，可用「張」為單位（例如 1張 = 1000股）',
    price='每股價格（元），留空則自動用目前市價',
    batch='一次輸入多筆買賣，例如：昇達科賣出5股2200 定穎投控賣出10股187（價格可省略，會用目前市價）'
)
@app_commands.choices(action=[
    app_commands.Choice(name='買入記錄', value='buy'),
    app_commands.Choice(name='賣出記錄', value='sell'),
    app_commands.Choice(name='批次買賣', value='batch'),
    app_commands.Choice(name='持股清單', value='list'),
    app_commands.Choice(name='損益查看', value='pnl'),
    app_commands.Choice(name='試算買入損益', value='calc_buy'),
    app_commands.Choice(name='試算賣出損益', value='calc_sell'),
    app_commands.Choice(name='刪除交易紀錄', value='delete'),
])
async def cmd_stock(interaction: discord.Interaction,
                    action: str, ticker: str = '',
                    shares: str = '', price: float = 0.0, batch: str = ''):
    if not await _check_guild(interaction): return
    a = action.lower().strip()
    await interaction.response.defer(ephemeral=True)
    loop = asyncio.get_event_loop()

    # buy / sell / calc 共用：股票可填代號或名稱，股數可用「張」
    resolved = (None, None)
    parsed_shares = None
    if a in ('buy', 'sell', 'calc_buy', 'calc_sell'):
        if ticker:
            resolved = await loop.run_in_executor(None, resolve_ticker, ticker)
            if resolved[0] is None:
                await interaction.followup.send(f'找不到股票「{ticker}」，請確認代號或名稱是否正確。', ephemeral=True)
                return
        if shares:
            parsed_shares = parse_shares(shares)
            if not parsed_shares:
                await interaction.followup.send('股數格式錯誤，可輸入「1000」或「1張」（= 1000 股）。', ephemeral=True)
                return

    if a == 'buy':
        if not resolved[0] or not parsed_shares:
            await interaction.followup.send(
                '請填股票、股數；股數可用「張」（1張 = 1000股），價格留空會自動用目前市價。\n'
                '例如：台積電、1張、900', ephemeral=True); return
        rticker, rname = resolved
        p = await loop.run_in_executor(None, fetch_price, rticker)
        name = _best_name(rticker, rname, p)
        actual_price = price if price > 0 else ((p.get('today_close') or p.get('yesterday_close')) if p else None)
        if not actual_price:
            await interaction.followup.send('查不到目前市價，請手動輸入價格。', ephemeral=True); return
        with db() as c:
            c.execute('INSERT INTO transactions (ticker,name,shares,cost,type) VALUES (?,?,?,?,?)',
                      (rticker, name, parsed_shares, actual_price, 'buy'))
        note = '（目前市價）' if price <= 0 else ''
        await interaction.followup.send(
            f'✅ 買入記錄\n**{name} {rticker}** × {parsed_shares:,}股 @ {actual_price:,.0f}元{note}\n'
            f'總成本：{parsed_shares*actual_price:,.0f}元', ephemeral=True)

    elif a == 'sell':
        if not resolved[0] or not parsed_shares:
            await interaction.followup.send(
                '請填股票、股數；股數可用「張」（1張 = 1000股），價格留空會自動用目前市價。\n'
                '例如：台積電、1張、950', ephemeral=True); return
        rticker, rname = resolved
        hs = get_holdings()
        h = next((x for x in hs if x['ticker'] == rticker), None)
        if not h or h['shares'] < parsed_shares:
            await interaction.followup.send(
                f'持股不足，{h["name"] if h else (rname or rticker)} 目前 {h["shares"] if h else 0} 股', ephemeral=True); return
        actual_price = price
        if actual_price <= 0:
            p = await loop.run_in_executor(None, fetch_price, rticker)
            actual_price = (p.get('today_close') or p.get('yesterday_close')) if p else None
        if not actual_price:
            await interaction.followup.send('查不到目前市價，請手動輸入價格。', ephemeral=True); return
        realized = (actual_price - h['avg_cost']) * parsed_shares
        with db() as c:
            c.execute('INSERT INTO transactions (ticker,name,shares,cost,type) VALUES (?,?,?,?,?)',
                      (rticker, h['name'], parsed_shares, actual_price, 'sell'))
        note = '（目前市價）' if price <= 0 else ''
        await interaction.followup.send(
            f'✅ 賣出記錄\n**{h["name"]} {rticker}** × {parsed_shares:,}股 @ {actual_price:,.0f}元{note}\n'
            f'實現損益：{signed(realized)}元 {color(realized)}', ephemeral=True)

    elif a == 'batch':
        if not batch.strip():
            await interaction.followup.send(
                '請在「batch」欄位一次輸入多筆買賣，例如：\n'
                '`昇達科賣出5股2200 定穎投控賣出10股187`\n'
                '（用空白分隔每筆，價格可省略則用目前市價）', ephemeral=True); return
        matches = list(_BATCH_TRADE_RE.finditer(batch))
        if not matches:
            await interaction.followup.send(
                '看不懂批次格式，請用「股票名稱/代號＋買入或賣出＋股數＋股＋價格」，例如：\n'
                '`昇達科賣出5股2200 定穎投控賣出10股187`', ephemeral=True); return
        results = []
        for m in matches:
            raw_name, act_word, shares_str, unit, price_str = m.groups()
            typ = 'buy' if act_word in ('買入', '買進', '加碼') else 'sell'
            rticker, rname = await loop.run_in_executor(None, resolve_ticker, raw_name)
            if not rticker:
                results.append(f'❌ 找不到「{raw_name}」')
                continue
            psh = parse_shares(f'{shares_str}{unit or "股"}')
            if not psh:
                results.append(f'❌ {raw_name}：股數格式錯誤')
                continue
            entered_price = float(price_str) if price_str else 0.0
            _, msg = await _execute_trade(loop, rticker, rname, psh, entered_price, typ)
            results.append(msg)
        await interaction.followup.send('📋 批次處理結果\n' + '\n'.join(results), ephemeral=True)

    elif a == 'list':
        hs = get_holdings()
        if not hs:
            await interaction.followup.send('目前沒有持股。', ephemeral=True); return
        lines = ['**目前持股**\n']
        for h in hs:
            p = await asyncio.get_event_loop().run_in_executor(None, fetch_price, h['ticker'])
            tc = (p.get('today_close') or p.get('yesterday_close')) if p else None
            pnl_str = ''
            if tc:
                pnl = (tc - h['avg_cost']) * h['shares']
                pp  = (tc - h['avg_cost']) / h['avg_cost'] * 100
                pnl_str = f'｜現價 {tc:.0f}｜損益 {signed(pnl)}（{signed(pp, ".2f")}%）{color(pnl)}'
            lines.append(f'**{h["name"]} {h["ticker"]}**：{h["shares"]:,}股 @ 均價 {h["avg_cost"]:.2f}{pnl_str}')
        await interaction.followup.send('\n'.join(lines), ephemeral=True)

    elif a == 'pnl':
        hs = get_holdings()
        if not hs:
            await interaction.followup.send('目前沒有持股。', ephemeral=True); return
        lines = ['**損益概覽**\n']
        tc_total = tv_total = 0.0
        for h in hs:
            p = await asyncio.get_event_loop().run_in_executor(None, fetch_price, h['ticker'])
            tc = (p.get('today_close') or p.get('yesterday_close')) if p else None
            cost = h['avg_cost'] * h['shares']
            val  = (tc * h['shares']) if tc else cost
            tc_total += cost; tv_total += val
            pnl = val - cost; pp = pnl / cost * 100 if cost else 0
            lines.append(
                f'**{h["name"]} {h["ticker"]}**\n'
                f'{h["shares"]:,}股｜均價 {h["avg_cost"]:.2f}｜現價 {tc or "?"}\n'
                f'損益 {signed(pnl)}元 {color(pnl)}（{signed(pp, ".2f")}%）\n'
            )
        total_pnl = tv_total - tc_total
        total_pp  = total_pnl / tc_total * 100 if tc_total else 0
        lines.append(
            f'──────────\n'
            f'總投入：{tc_total:,.0f}元\n'
            f'總市值：{tv_total:,.0f}元\n'
            f'總損益：{signed(total_pnl)}元 {color(total_pnl)}（{signed(total_pp, ".2f")}%）'
        )
        await interaction.followup.send('\n'.join(lines), ephemeral=True)

    elif a == 'calc_sell':
        if not resolved[0] or not parsed_shares:
            await interaction.followup.send(
                '請填股票、股數；股數可用「張」（1張 = 1000股），價格留空會自動用目前市價。\n'
                '例如：台積電、1張、1200', ephemeral=True); return
        rticker, rname = resolved
        hs = get_holdings()
        h = next((x for x in hs if x['ticker'] == rticker), None)
        if not h:
            await interaction.followup.send(f'找不到 {rname or rticker} 的持股紀錄。', ephemeral=True); return
        if h['shares'] < parsed_shares:
            await interaction.followup.send(f'持股不足，{h["name"]} 目前 {h["shares"]} 股', ephemeral=True); return
        actual_price = price
        if actual_price <= 0:
            p = await loop.run_in_executor(None, fetch_price, rticker)
            actual_price = (p.get('today_close') or p.get('yesterday_close')) if p else None
        if not actual_price:
            await interaction.followup.send('查不到目前市價，請手動輸入價格。', ephemeral=True); return
        pnl = (actual_price - h['avg_cost']) * parsed_shares
        pp  = (actual_price - h['avg_cost']) / h['avg_cost'] * 100
        note = '（目前市價）' if price <= 0 else ''
        await interaction.followup.send(
            f'📊 試算賣出（不動資料）\n**{h["name"]} {rticker}**\n'
            f'賣出 {parsed_shares:,}股 @ {actual_price:,.0f}元{note} | 均價 {h["avg_cost"]:.2f}\n'
            f'損益 {signed(pnl)}元 {color(pnl)}（{signed(pp, ".2f")}%）', ephemeral=True)

    elif a == 'calc_buy':
        if not resolved[0] or not parsed_shares:
            await interaction.followup.send(
                '請填股票、股數；股數可用「張」（1張 = 1000股），價格留空會自動用目前市價。\n'
                '例如：台積電、1張、900', ephemeral=True); return
        rticker, rname = resolved
        hs = get_holdings()
        h = next((x for x in hs if x['ticker'] == rticker), None)
        p = await loop.run_in_executor(None, fetch_price, rticker)
        market_price = (p.get('today_close') or p.get('yesterday_close')) if p else None
        actual_price = price if price > 0 else market_price
        if not actual_price:
            await interaction.followup.send('查不到目前市價，請手動輸入價格。', ephemeral=True); return
        if not market_price:
            await interaction.followup.send('查不到目前市價，無法試算買入後損益。', ephemeral=True); return
        old_shares, old_cost = (h['shares'], h['avg_cost']) if h else (0, 0.0)
        new_shares = old_shares + parsed_shares
        new_avg_cost = (old_cost * old_shares + actual_price * parsed_shares) / new_shares
        name = h['name'] if h else _best_name(rticker, rname, p)
        pnl = (market_price - new_avg_cost) * new_shares
        pp  = (market_price - new_avg_cost) / new_avg_cost * 100
        note = '（目前市價）' if price <= 0 else ''
        holding_line = f'原持有 {old_shares:,}股 @ 均價 {old_cost:.2f}\n' if old_shares else ''
        await interaction.followup.send(
            f'📊 試算買入（不動資料）\n**{name} {rticker}**\n'
            f'{holding_line}'
            f'買入 {parsed_shares:,}股 @ {actual_price:,.0f}元{note}\n'
            f'本次成本：{parsed_shares*actual_price:,.0f}元\n'
            f'買入後均價：{new_avg_cost:.2f}｜目前市價：{market_price:,.0f}\n'
            f'損益 {signed(pnl)}元 {color(pnl)}（{signed(pp, ".2f")}%）', ephemeral=True)

    elif a == 'delete':
        if not ticker:
            with db() as c:
                rows = c.execute(
                    'SELECT id,ticker,name,shares,cost,type,created FROM transactions ORDER BY id DESC LIMIT 15'
                ).fetchall()
            lines = ['**最近交易紀錄**（`/stock delete <ID>` 刪除）\n']
            for row in rows:
                lines.append(f'`{row[0]}` {row[5]} **{row[2]} {row[1]}** {row[3]}股@{row[4]:.0f} ({row[6][:10]})')
            await interaction.followup.send('\n'.join(lines), ephemeral=True)
        elif ticker.isdigit():
            with db() as c:
                c.execute('DELETE FROM transactions WHERE id=?', (int(ticker),))
            await interaction.followup.send(f'🗑️ 已刪除紀錄 #{ticker}', ephemeral=True)
        else:
            await interaction.followup.send('請填交易 ID（數字），或不填查看紀錄。', ephemeral=True)
    else:
        await interaction.followup.send('可用：`buy` / `sell` / `batch` / `list` / `pnl` / `calc_buy` / `calc_sell` / `delete`', ephemeral=True)

# ── 設定指令 ──────────────────────────────────────────────────
@tree.command(name='設定', description='設定推送時間、週報時間與頻道')
@app_commands.rename(key='項目', value='數值')
@app_commands.describe(
    key='選擇要設定的項目',
    value='時間填 HH:MM；週報星期可填 週日/禮拜日/日/0/7；頻道填頻道 ID'
)
@app_commands.choices(key=[
    app_commands.Choice(name='每日推送時間', value='push_time'),
    app_commands.Choice(name='週報時間', value='weekly_time'),
    app_commands.Choice(name='週報星期', value='weekly_day'),
    app_commands.Choice(name='推送頻道', value='channel'),
])
async def cmd_config(interaction: discord.Interaction, key: str, value: str):
    if not await _check_guild(interaction): return
    k = key.lower().strip()
    if k == 'push_time':
        if not _valid_hhmm(value):
            await interaction.response.send_message('格式：HH:MM，例如 `08:30`，小時 00-23、分鐘 00-59。', ephemeral=True); return
        set_cfg('push_time', value)
        await interaction.response.send_message(f'✅ 每日推送時間設為 {value}', ephemeral=True)
    elif k == 'weekly_time':
        if not _valid_hhmm(value):
            await interaction.response.send_message('格式：HH:MM，例如 `18:00`，小時 00-23、分鐘 00-59。', ephemeral=True); return
        set_cfg('weekly_time', value)
        day = _parse_weekday(get_cfg('weekly_day', '日'))
        await interaction.response.send_message(f'✅ 週報時間設為 {_weekday_label(day if day is not None else 6)} {value}', ephemeral=True)
    elif k == 'weekly_day':
        day = _parse_weekday(value)
        if day is None:
            await interaction.response.send_message('週報星期格式可填：`週日`、`禮拜日`、`日`、`0` 或 `7`（週日），也可填 `1` 到 `6`。', ephemeral=True); return
        set_cfg('weekly_day', _weekday_label(day))
        await interaction.response.send_message(f'✅ 週報星期設為 {_weekday_label(day)}', ephemeral=True)
    elif k == 'channel':
        set_cfg('channel_id', value)
        await interaction.response.send_message(f'✅ 推送頻道設為 <#{value}>', ephemeral=True)
    else:
        await interaction.response.send_message('可設定：`push_time` / `weekly_time` / `weekly_day` / `channel`', ephemeral=True)

# ── 學習指令 ──────────────────────────────────────────────────
@tree.command(name='學習', description='查詢台股術語，填 reset 重置學習紀錄')
@app_commands.rename(term='術語')
@app_commands.describe(term='術語名稱（空白列出全部）')
async def cmd_learn(interaction: discord.Interaction, term: str = ''):
    if not await _check_guild(interaction): return
    t = term.strip()
    if t.lower() == 'reset':
        with db() as c:
            c.execute('DELETE FROM learned_terms')
        await interaction.response.send_message('✅ 已重置，下次推送會重新顯示新手說明。', ephemeral=True); return

    if not t:
        cats = {
            '技術指標': ['MA','KD','MACD','RSI','布林通道','支撐','壓力','突破','跌破','缺口','量能'],
            '籌碼面':   ['外資','投信','自營商','三大法人','買超','賣超','融資','融券'],
            '基本面':   ['本益比','EPS','毛利率','ROE','殖利率','除息','配息','法說會'],
            '市場':     ['大盤','漲停','跌停','多頭','空頭','多空','盤整','量縮','量增','當沖'],
            '產業':     ['CoWoS','HBM','ODM','晶圓代工','封測','AI 伺服器','低軌衛星','儲能'],
            '操作':     ['停損','停利','加碼','減碼','攤平','套牢','解套','波段'],
        }
        lines = ['**📚 台股術語字典** — `/learn <術語>` 查詢說明\n']
        for cat, terms in cats.items():
            lines.append(f'**{cat}**：' + '、'.join(terms))
        await interaction.response.send_message('\n'.join(lines), ephemeral=True); return

    expl = TERMS.get(t)
    if not expl:
        matches = [(k, v) for k, v in TERMS.items() if t in k or k in t][:3]
        if matches:
            await interaction.response.send_message(
                '\n\n'.join(f'**{k}**：{v}' for k, v in matches), ephemeral=True)
        else:
            await interaction.response.send_message(f'找不到「{t}」，輸入 `/learn` 查看所有術語。', ephemeral=True)
        return

    with db() as c:
        c.execute('INSERT OR IGNORE INTO learned_terms (term) VALUES (?)', (t,))
    await interaction.response.send_message(f'**📖 {t}**\n{expl}', ephemeral=True)

# ── 手動推送 ──────────────────────────────────────────────────
@tree.command(name='推送', description='立即推送今日市場報告')
async def cmd_push(interaction: discord.Interaction):
    if not await _check_guild(interaction): return
    channel_id = int(get_cfg('channel_id') or str(PUSH_CHANNEL_ID))
    channel = bot.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message('找不到頻道，請先 `/config channel <ID>`。', ephemeral=True); return
    await interaction.response.send_message('⏳ 產生報告中，約需 30 秒…', ephemeral=True)
    try:
        embed = await asyncio.get_event_loop().run_in_executor(None, build_report)
        await channel.send(embed=embed)
    except Exception as e:
        log.error(f'手動推送失敗: {e}', exc_info=True)
        await channel.send(f'⚠️ 推送失敗：{e}')

# ── 週報指令 ──────────────────────────────────────────────────
@tree.command(name='週報', description='產生本週市場回顧')
async def cmd_weekly(interaction: discord.Interaction):
    if not await _check_guild(interaction): return
    await interaction.response.defer(ephemeral=True)
    embed = await asyncio.get_event_loop().run_in_executor(None, build_weekly_report)
    channel_id = int(get_cfg('channel_id') or str(PUSH_CHANNEL_ID))
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(embed=embed)
        await interaction.followup.send('✅ 週報已發送。', ephemeral=True)
    else:
        await interaction.followup.send(embed=embed)

# ── 個股分析 ──────────────────────────────────────────────────
def build_stock_analysis(ticker: str, display_name: str = '') -> discord.Embed | None:
    """抓個股資料並用 AI 分析，回傳 Embed；找不到股票回傳 None"""
    from concurrent.futures import ThreadPoolExecutor

    ticker = ticker.strip().upper()
    label  = display_name or ticker

    with ThreadPoolExecutor(max_workers=4) as ex:
        price_fut = ex.submit(fetch_price, ticker)
        inst_fut  = ex.submit(fetch_institutional, ticker)
        news_fut  = ex.submit(scrape_stock_news, ticker, label, 4)
        profile_fut = ex.submit(fetch_stock_profile, ticker, label)

    p    = price_fut.result()
    inst = inst_fut.result()
    news = news_fut.result()
    profile = profile_fut.result()

    if not p and not profile.get('name'):
        return None
    p = p or {}

    tc   = p.get('today_close')
    yc   = p.get('yesterday_close')
    cur  = tc or yc
    is_rt = p.get('is_realtime', False)
    price_label = '即時' if is_rt else ('今收' if tc else '昨收')

    dc = (tc - yc) if (tc and yc) else None
    dp = dc / yc * 100 if (dc is not None and yc) else None

    # 從 DB 查持有資訊
    holdings = {h['ticker']: h for h in get_holdings()}
    holding  = holdings.get(ticker)

    # AI 分析
    price_info = f"目前價格 {cur:.0f} 元（{price_label}）" if cur else "目前無價格資料"
    profile_bits = []
    if profile.get('industry_category'):
        profile_bits.append(f"FinMind 產業分類：{profile['industry_category']}")
    if profile.get('market_type'):
        profile_bits.append(f"市場別：{profile['market_type']}")
    if profile.get('english_name'):
        profile_bits.append(f"英文名稱：{profile['english_name']}")
    if profile.get('sector') or profile.get('industry'):
        profile_bits.append(f"Yahoo 分類：{profile.get('sector') or '未知'} / {profile.get('industry') or '未知'}")
    if profile.get('summary'):
        profile_bits.append(f"Yahoo 公司摘要：{profile['summary'][:700]}")
    profile_info = '；'.join(profile_bits) if profile_bits else '暫無基本資料'
    inst_info  = ''
    if inst and any(v != 0 for v in inst.values()):
        inst_info = (f"外資 {inst['foreign']/1e8:+.2f}億、"
                     f"投信 {inst['trust']/1e8:+.2f}億、"
                     f"自營 {inst['dealer']/1e8:+.2f}億")
    news_info = '、'.join(news[:3]) if news else '暫無新聞'
    ai_text = ask_ai(
        f"你是台股投資顧問，請用繁體中文分析台股 {label}({ticker})（約 200 字）。\n"
        f"股票官方名稱是「{label}」，代號是「{ticker}」。不得改成其他公司名稱，也不得把代號解讀成別家公司。\n\n"
        f"基本資料：{profile_info}\n"
        f"市場資料：{price_info}{'；法人：' + inst_info if inst_info else ''}；近期新聞：{news_info}\n\n"
        f"請包含：\n"
        f"1.【產業定位】根據基本資料說明產業和主要業務，英文摘要可以翻成自然繁體中文\n"
        f"2.【台積電關聯】根據產業和業務判斷是否為供應商/客戶/無直接關聯；不確定就寫無明確資料\n"
        f"3.【近況分析】只根據上方價格、法人、新聞資料分析；沒有資料不要補財報或市場趨勢\n"
        f"4.【操作提示】短線/長線建議一句話，理由必須連結上方已提供資料\n\n"
        f"語氣適合新手，不要加免責聲明，不要編造未提供的財報、產品或新聞。",
        max_tokens=500,
    )

    # 組 Embed
    title_price = f'{cur:.0f}元' if cur else '—'
    embed = discord.Embed(
        title=f'🔍 個股分析｜{label} {ticker}　{title_price}',
        color=0x2ECC71 if (dc and dc > 0) else (0xE74C3C if (dc and dc < 0) else 0x95A5A6)
    )

    basic_lines = []
    if profile.get('market_type'):
        basic_lines.append(f"市場別：{profile['market_type']}")
    if profile.get('industry_category'):
        basic_lines.append(f"產業：{profile['industry_category']}")
    if profile.get('industry'):
        basic_lines.append(f"Yahoo：{profile['industry']}")
    if profile.get('website'):
        basic_lines.append(f"網站：{profile['website']}")
    if basic_lines:
        embed.add_field(name='🏢 基本資料', value='\n'.join(basic_lines)[:1024], inline=False)

    # 價格區
    price_lines = []
    if tc and yc:
        price_lines.append(f'昨收 {yc:.0f} → {price_label} {tc:.0f}元 {arrow(dc) if dc else ""}')
    elif yc:
        price_lines.append(f'收盤 {yc:.0f}元（今日資料待更新）')
    if dc is not None and dp is not None:
        price_lines.append(f'日漲跌 {signed(dc)}元（{signed(dp, ".2f")}%）{color(dc)}')
    if is_rt:
        price_lines.append('*即時報價，約 15 分鐘延遲*')
    embed.add_field(name='📈 價格', value='\n'.join(price_lines) or '—', inline=True)

    # 持有資訊（若有）
    if holding and cur:
        avg = holding['avg_cost']
        sh  = holding['shares']
        pnl = (cur - avg) * sh
        pp  = (cur - avg) / avg * 100
        embed.add_field(
            name='💼 我的持股',
            value=f'持有 {sh} 股\n成本 {avg:.2f} → 現價 {cur:.0f}元\n損益 {signed(pnl)}元（{signed(pp, ".1f")}%）{color(pnl)}',
            inline=True
        )

    # 法人
    if inst and any(v != 0 for v in inst.values()):
        def fi(v): return f'{signed(v/1e8, ".2f")}億 {color(v)}'
        embed.add_field(
            name='🏦 三大法人',
            value=f'外資 {fi(inst["foreign"])}\n投信 {fi(inst["trust"])}\n自營 {fi(inst["dealer"])}',
            inline=True
        )

    # 新聞
    if news:
        embed.add_field(
            name='📰 近期新聞',
            value='\n'.join(f'・{n}' for n in news[:4]),
            inline=False
        )

    # AI 分析
    embed.add_field(name='🤖 AI 分析', value=ai_text[:1024], inline=False)
    embed.set_footer(text='⚠️ 以上為 AI 輔助參考，不構成投資建議。')
    return embed

async def stock_query_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not _guild_allowed(interaction.guild_id or 0):
        return []
    loop = asyncio.get_running_loop()
    candidates = await loop.run_in_executor(None, find_ticker_candidates, current, 20)
    return [
        app_commands.Choice(name=f'{name} ({code})'[:100], value=code)
        for code, name in candidates[:20]
    ]

@tree.command(name='分析', description='分析指定股票的產業定位、法人動向與 AI 建議')
@app_commands.describe(查詢='股票代號或名稱，例如 2330 或 台積電')
@app_commands.autocomplete(查詢=stock_query_autocomplete)
async def cmd_analyze(interaction: discord.Interaction, 查詢: str):
    if not await _check_guild(interaction): return
    await interaction.response.defer()
    loop = asyncio.get_event_loop()

    def _run():
        ticker, name = resolve_ticker(查詢.strip())
        if ticker is None:
            return None, 查詢
        return build_stock_analysis(ticker, name or ticker), None

    embed, bad_query = await loop.run_in_executor(None, _run)
    if embed is None:
        candidates = await loop.run_in_executor(None, find_ticker_candidates, 查詢, 8)
        if candidates:
            candidate_lines = '\n'.join(f'`{code}` {name}' for code, name in candidates)
            msg = (
                f'找不到唯一股票「{bad_query}」。請改用更完整名稱或代號，例如：\n'
                f'{candidate_lines}'
            )
        else:
            msg = f'找不到股票「{bad_query}」，請確認代號或名稱是否正確。'
        await interaction.followup.send(
            msg, ephemeral=True
        )
    else:
        await interaction.followup.send(embed=embed)

# ── 定時推送 ──────────────────────────────────────────────────
@tasks.loop(minutes=1)
async def daily_push():
    now = datetime.datetime.now()
    push_time = get_cfg('push_time', '08:30')
    if not _valid_hhmm(push_time):
        log.warning(f'每日推送時間格式錯誤：{push_time}')
        return
    h, m = map(int, push_time.split(':'))
    if now.hour != h or now.minute != m or now.weekday() > 4:
        return
    channel_id = int(get_cfg('channel_id') or str(PUSH_CHANNEL_ID))
    channel = bot.get_channel(channel_id)
    if not channel: return
    try:
        embed = await asyncio.get_event_loop().run_in_executor(None, build_report)
        await channel.send(embed=embed)
    except Exception as e:
        log.error(f'定時推送失敗: {e}', exc_info=True)

@tasks.loop(minutes=1)
async def weekly_push():
    now = datetime.datetime.now()
    weekly_time = get_cfg('weekly_time', '18:00')
    weekly_day = _parse_weekday(get_cfg('weekly_day', '日'))
    if weekly_day is None:
        log.warning(f'週報星期格式錯誤：{get_cfg("weekly_day", "日")}')
        return
    if not _valid_hhmm(weekly_time):
        log.warning(f'週報時間格式錯誤：{weekly_time}')
        return
    h, m = map(int, weekly_time.split(':'))
    if now.weekday() != weekly_day or now.hour != h or now.minute != m:
        return

    today_key = now.date().isoformat()
    if get_cfg('weekly_last_push_date') == today_key:
        return

    channel_id = int(get_cfg('channel_id') or str(PUSH_CHANNEL_ID))
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    try:
        embed = await asyncio.get_event_loop().run_in_executor(None, build_weekly_report)
        await channel.send(embed=embed)
        set_cfg('weekly_last_push_date', today_key)
    except Exception as e:
        log.error(f'週報定時推送失敗: {e}', exc_info=True)

@daily_push.before_loop
async def before_daily_push():
    await bot.wait_until_ready()

@weekly_push.before_loop
async def before_weekly_push():
    await bot.wait_until_ready()

# ── 主程式 ────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    log.info('DB 初始化完成')
    if not DISCORD_TOKEN:
        log.error('DISCORD_TOKEN 未設定'); exit(1)
    try:
        with open(PID_FILE, 'w', encoding='ascii') as f:
            f.write(str(os.getpid()))
    except Exception:
        pass
    try:
        bot.run(DISCORD_TOKEN)
    finally:
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass

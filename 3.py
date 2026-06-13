# ==============================================================================
#  TWITCH BOT V5.1.0 (多頻道隔離 + 官方彩色公告 + 極致效能重構版)
# ==============================================================================

import asyncio, datetime, json, logging, os, random, re, shutil, sys, time, calendar, threading, hashlib
from urllib.parse import quote
from functools import wraps
from logging.handlers import TimedRotatingFileHandler
import twitchio.websocket
from twitchio.ext import commands
from twitchio.ext.commands.errors import CommandNotFound, CommandOnCooldown
import aiohttp, aiosqlite
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import atexit
import subprocess

# --- Selenium 相關組件 ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ----------------------------------------------------------------
# [0] 環境與全域設定
# ----------------------------------------------------------------
load_dotenv()
BOT_VERSION = "5.1.0"

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

CLIENT_ID, CLIENT_SECRET, TWITCH_ACCESS_TOKEN = os.getenv("TWITCH_CLIENT_ID"), os.getenv("TWITCH_CLIENT_SECRET"), os.getenv("TWITCH_ACCESS_TOKEN")
env_access, env_refresh = os.getenv("TWITCH_USER_ACCESS_TOKEN"), os.getenv("TWITCH_USER_REFRESH_TOKEN")

BOT_ADMINS = {a.strip().lower() for a in os.getenv("BOT_ADMINS", "").split(",") if a.strip()}
CHANNELS_STR = os.getenv("CHANNELS", "")
INITIAL_CHANNELS = [c.strip().lower() for c in CHANNELS_STR.split(",") if c.strip()]
ALLOWED_USERS = {u.strip().lower() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()}
ANNOUNCE_CHANNELS = {c.strip().lower() for c in os.getenv("ANNOUNCE_CHANNELS", CHANNELS_STR).split(",") if c.strip()}
SILENT_CHANNELS = {c.strip().lower() for c in os.getenv("SILENT_CHANNELS", "").split(",") if c.strip()}

# === 🟢 斗內監聽設定 (全面改為自動讀取 .env) ===
ENABLE_OPAY   = os.getenv('ENABLE_OPAY', 'True').lower() == 'true'
ENABLE_ECPAY  = os.getenv('ENABLE_ECPAY', 'True').lower() == 'true'
ENABLE_PAYPAL = os.getenv('ENABLE_PAYPAL', 'False').lower() == 'true'

URL_OPAY   = os.getenv('URL_OPAY', '')
URL_ECPAY  = os.getenv('URL_ECPAY', '')
URL_PAYPAL = os.getenv('URL_PAYPAL', '')

# 讀取發送目標頻道，如果留空就會是空陣列
DONATION_TARGETS_STR = os.getenv("DONATION_TARGET_CHANNELS", "")
DONATION_TARGET_CHANNELS = [c.strip().lower() for c in DONATION_TARGETS_STR.split(",") if c.strip()]
BANNED_WORDS_STR = os.getenv("BANNED_WORDS", "")
BANNED_WORDS = [w.strip() for w in BANNED_WORDS_STR.replace('\n', ',').split(",") if w.strip()]
STRICT_PATTERNS_STR = os.getenv("STRICT_BANNED_PATTERNS", "")
STRICT_PATTERNS = [p.strip() for p in STRICT_PATTERNS_STR.split("||") if p.strip()]
IGNORED_BOTS_STR = os.getenv("IGNORED_BOTS", "nightbot,streamelements,fossabot,soundalerts")
IGNORED_BOTS = {b.strip().lower() for b in IGNORED_BOTS_STR.split(",") if b.strip()}
PROTECTED_EMOTES_STR = os.getenv("PROTECTED_TWITCH_EMOTES", "GoldPLZ,DinoDance,HolidayPresent,GlitchCat,ItsBoshyTime,imGlitch,BloodTrail,cmonBruh")
PROTECTED_TWITCH_EMOTES = [e.strip() for e in PROTECTED_EMOTES_STR.split(",") if e.strip()]
# ===============================================

LOCAL_TZ = datetime.datetime.now().astimezone().tzinfo
LOG_RETAIN_DAYS = int(os.getenv("LOG_RETAIN_DAYS", 5))
BACKUP_RETAIN_DAYS = int(os.getenv("BACKUP_RETAIN_DAYS", 5))
TOP5_RETAIN_MONTHS = int(os.getenv("TOP5_RETAIN_MONTHS", 6))
WARMUP_DURATION, TIMEOUT_WARMUP = 1800, 60
TIMEOUT_STABLE = int(os.getenv("SILENCE_TIMEOUT", 180))
SILENCE_RECONNECT_LIMIT = int(os.getenv("SILENCE_RECONNECT_LIMIT", 2))
RESET_DELAY_SECONDS = int(os.getenv("RESET_DELAY_SECONDS", 60))
INTERVAL_REGULAR = 1200
API_FAIL_RESTART_SECONDS = int(os.getenv("API_FAIL_RESTART_SECONDS", 600))
OFFLINE_KEEPALIVE_INTERVAL = int(os.getenv("OFFLINE_KEEPALIVE_INTERVAL", 600))
CHAT_MESSAGE_API_SCOPE = "user:read:chat user:write:chat user:bot"
REQUIRED_USER_TOKEN_SCOPES = {
    "chat:read": "IRC 讀取聊天室",
    "chat:edit": "IRC 發送訊息",
    "user:bot": "聊天機器人身份授權",
    "user:write:chat": "Chat Message API 發話",
}

STATIC_ANNOUNCEMENTS = [
    " GoldPLZ 歡迎簽到！全部的指令列表在這：https://tinyurl.com/2d3zf8fy",
    "所有指令:!cu !運勢 !吸一口 !聲帶 !600 !dc !訂閱 !幫助 !求婚 @對象| !B人(詳細請!幫助)"
]

# 🟢 靜態資料全域化 (記憶體優化)
HAREM_TITLES = [
    "正宮娘娘", "皇貴妃", "貴妃", "德妃", "賢妃",
    "婕妤", "昭儀", "美人", "才人", "選侍", "淑女",
]
FORTUNES_LIST = [
    ("大吉", "🌟 爽啦！今天運氣超好，買彩券搞不好會中。"),
    ("中吉", "☀️ 順順的，今天沒遇到什麼破事。"),
    ("小吉", "🌤️ 還不錯，喝手搖飲可能會吸到雙倍珍珠。"),
    ("末吉", "☁️ 有點卡卡的，遇到雷隊友請先深呼吸。"),
    ("凶",   "🌧️ 超衰，今天不管幹嘛都很容易出包。"),
    ("大凶", "⛈️ 慘到爆，建議今天直接請假在家躺平。"),
]
HAIR_STATUS_LIST = [
    "今天有洗頭啦！頭髮超順超香的 ✨",
    "瀏海油到變條碼了，超崩潰。",
    "狂噴乾洗髮，假裝自己有洗頭。",
    "戴帽子掩飾一切，誰知道我幾天沒洗。",
    "頭油到可以煎蛋了，但還是不想洗。",
    "反正明天放假不出門，今天絕對不洗！",
    "拿下安全帽頭髮直接扁掉，超醜。",
    "只洗瀏海騙騙大家，女生都懂的絕招。",
]
COLORS_LIST = [
    "紅色", "藍色", "黃色", "綠色", "白色", "黑色",
    "橘色", "紫色", "粉紅色", "奶茶色", "廢土色", "天空藍",
    "素顏的顏色", "油亮色", "蒼白色", "紙箱色", "消光黑", "大便色",
]
TIMES_LIST = [
    "子時 (23:00-01:00)", "丑時 (01:00-03:00)", "寅時 (03:00-05:00)",
    "卯時 (05:00-07:00)", "辰時 (07:00-09:00)", "巳時 (09:00-11:00)",
    "午時 (11:00-13:00)", "未時 (13:00-15:00)", "申時 (15:00-17:00)",
    "酉時 (17:00-19:00)", "戌時 (19:00-21:00)", "亥時 (21:00-23:00)",
]

RATES = {'USD': 32.5, '$': 32.5, 'JPY': 0.22, '¥': 0.22, 'EUR': 35.0, '€': 35.0, 'GBP': 41.0, '£': 41.0, 'KRW': 0.024}
CHROME_PROFILE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chrome_profiles")

if not INITIAL_CHANNELS or not all([CLIENT_ID, CLIENT_SECRET]):
    print("❌ 錯誤：未設定 CHANNELS 或 Client ID/Secret (請檢查 .env)")
    sys.exit(1)

# ----------------------------------------------------------------
# [0.1] 日誌系統與 TwitchIO 修補
# ----------------------------------------------------------------
os.makedirs("data/logs", exist_ok=True)

class CleanConsoleHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream); self.countdown_msg = ""
    def emit(self, record):
        try:
            msg = self.format(record)
            if "Websocket connection was closed" in msg: return
            self.stream.write("\r\033[K" + f"{msg}\n" + self.countdown_msg); self.flush()
        except: self.handleError(record)

def setup_logging():
    fmt = logging.Formatter(fmt="%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    logger = logging.getLogger(); logger.setLevel(logging.INFO)
    if logger.hasHandlers(): logger.handlers.clear()
    for name in ["twitchio", "twitchio.websocket", "twitchio.client", "urllib3", "selenium", "WDM"]:
        logging.getLogger(name).setLevel(logging.CRITICAL)
    fh = TimedRotatingFileHandler("data/logs/bot.log", when="midnight", interval=1, backupCount=LOG_RETAIN_DAYS, encoding="utf-8")
    eh = TimedRotatingFileHandler("data/logs/error.log", when="midnight", interval=1, backupCount=LOG_RETAIN_DAYS, encoding="utf-8")
    ch = CleanConsoleHandler(sys.stdout)
    fh.setFormatter(fmt); eh.setFormatter(fmt); ch.setFormatter(fmt); eh.setLevel(logging.WARNING)
    logger.addHandler(fh); logger.addHandler(eh); logger.addHandler(ch)

setup_logging()

def fix_twitchio_bug():
    orig_handle = twitchio.websocket.WSConnection._join_future_handle
    async def patched(self, ch: str, fut: asyncio.Future, to: float = 10.0):
        try: await orig_handle(self, ch, fut, to)
        except (KeyError, asyncio.TimeoutError, asyncio.CancelledError):
            if hasattr(self, '_join_pending'): self._join_pending.pop(ch, None)
        except Exception as e: logging.error(f"⚠️ [Hotfix] Join Error: {e}")
    twitchio.websocket.WSConnection._join_future_handle = patched

    orig_join = twitchio.websocket.WSConnection._join_channel
    async def patched_join(self, *args, **kwargs):
        try:
            await orig_join(self, *args, **kwargs)
        except (ConnectionResetError, aiohttp.ClientConnectorError): pass
        except Exception as e:
            if "closing transport" not in str(e): logging.error(f"⚠️ [Hotfix] Join Channel Error: {e}")
    twitchio.websocket.WSConnection._join_channel = patched_join

    orig_task_callback = twitchio.websocket.WSConnection._task_callback
    def patched_task_callback(self, data, task):
        if task.cancelled():
            return
        try:
            return orig_task_callback(self, data, task)
        except asyncio.CancelledError:
            return
    twitchio.websocket.WSConnection._task_callback = patched_task_callback

fix_twitchio_bug()

async def initialize_tokens_async():
    logging.info("🔄 檢查 Token 中 (完全非同步啟動)...")
    db_acc = db_ref = None
    try:
        async with aiosqlite.connect("checkin.db") as db:
            async with db.execute("SELECT value FROM bot_state WHERE key='USER_ACCESS_TOKEN'") as c:
                if row := await c.fetchone(): db_acc = row[0]
            async with db.execute("SELECT value FROM bot_state WHERE key='USER_REFRESH_TOKEN'") as c:
                if row := await c.fetchone(): db_ref = row[0]
    except: pass

    async def validate(tk, label="Token"):
        """回傳 data dict 表示成功，"scope_error" 表示 token 有效但缺少必要權限，None 表示 token 無效或過期。"""
        if not tk: return None
        try:
            async with aiohttp.ClientSession() as s, s.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {tk.replace('oauth:', '')}"}) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                scopes = set(data.get("scopes", []))
                missing = [name for scope, name in REQUIRED_USER_TOKEN_SCOPES.items() if scope not in scopes]
                if missing:
                    logging.error(f"❌ {label} 缺少必要權限：{', '.join(missing)}。")
                    return "scope_error"
                return data
        except Exception as e:
            logging.error(f"❌ {label} 驗證失敗：{e}")
            return None

    async def save(acc, ref):
        try:
            async with aiosqlite.connect("checkin.db") as db:
                await db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", ("USER_ACCESS_TOKEN", acc))
                if ref: await db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", ("USER_REFRESH_TOKEN", ref))
                await db.commit()
        except: pass

    env_v = await validate(env_access, ".env Token") if env_access else None
    db_v = await validate(db_acc, "資料庫 Token") if db_acc else None

    if env_v and env_v != "scope_error":
        logging.info("✅ 檢測通過：使用 .env 設定的 Token"); await save(env_access, env_refresh)
        return env_access, env_refresh, f"oauth:{env_access.replace('oauth:', '')}"
    elif db_v and db_v != "scope_error":
        logging.info("✅ 檢測通過：使用 資料庫 儲存的 Token")
        return db_acc, db_ref or env_refresh, f"oauth:{db_acc.replace('oauth:', '')}"

    # 若任一 token 有效但缺少 scope，刷新無法補救，直接要求重新授權
    if env_v == "scope_error" or db_v == "scope_error":
        logging.error("❌ 現有 Token 缺少必要權限，刷新無法修復。請重新執行 authorize_chat_badge.bat 取得完整授權。")
        return None, None, None

    logging.warning("⚠️ 所有 Token 皆失效，嘗試刷新...")

    async def try_refresh(ref_tok, label):
        if not ref_tok: return None
        try:
            async with aiohttp.ClientSession() as s, s.post("https://id.twitch.tv/oauth2/token", data={"grant_type": "refresh_token", "refresh_token": ref_tok, "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}) as r:
                if r.status != 200: return None
                d = await r.json()
                v = await validate(d["access_token"], f"刷新後 Token ({label})")
                if v and v != "scope_error":
                    new_ref = d.get("refresh_token", ref_tok)
                    await save(d["access_token"], new_ref)
                    logging.info(f"🔧 Token 已自動修復並存檔 (使用 {label})")
                    return d["access_token"], new_ref, f"oauth:{d['access_token'].replace('oauth:', '')}"
                if v == "scope_error":
                    logging.error(f"❌ {label} 刷新後 Token 仍缺少必要權限，請重新執行 authorize_chat_badge.bat 取得完整授權。")
        except Exception as e:
            logging.error(f"❌ {label} 刷新失敗：{e}")
        return None

    # 優先用資料庫刷新金鑰（由 authorize_chat_badge.bat 寫入，scope 完整）；再試 .env 的
    refreshed = await try_refresh(db_ref, "資料庫刷新金鑰")
    if not refreshed and env_refresh and env_refresh != db_ref:
        refreshed = await try_refresh(env_refresh, ".env 刷新金鑰")
    if refreshed:
        return refreshed

    fallback_token = os.getenv("TWITCH_TOKEN")
    if fallback_token:
        fv = await validate(fallback_token, ".env TWITCH_TOKEN")
        if fv and fv != "scope_error":
            logging.warning("⚠️ 使用 .env TWITCH_TOKEN fallback 啟動。建議重新執行 authorize_chat_badge.bat 更新資料庫 token。")
            return fallback_token, None, fallback_token

    logging.error("❌ Token 刷新失敗或權限不足，停止啟動。請重新執行 authorize_chat_badge.bat 取得完整授權。")
    return None, None, None

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
LATEST_USER_TOKEN, LATEST_REFRESH_TOKEN, TWITCH_IRC_TOKEN = loop.run_until_complete(initialize_tokens_async())
if not TWITCH_IRC_TOKEN:
    logging.error("❌ 沒有可用的 Twitch 聊天 Token，BOT 不會啟動。")
    sys.exit(1)

# 每次啟動（含 os.execv 重啟）都更新 PID 檔，讓 update_bot.bat 能正確殺掉舊 process
try:
    _repo_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    _pid_paths = [
        os.path.join(_repo_root, "bot.pid"),
        os.path.join(os.path.dirname(_repo_root), "bot.pid"),
    ]
    for _pid_path in _pid_paths:
        with open(_pid_path, "w") as _f:
            _f.write(str(os.getpid()))
except Exception as _e:
    logging.warning(f"⚠️ 無法寫入 bot.pid: {_e}")

# ----------------------------------------------------------------
# [0.2] 資料庫核心
# ----------------------------------------------------------------
class Database:
    def __init__(self, db_name="checkin.db"):
        self.db_name = db_name
        self.conn = None

    async def connect(self):
        if not self.conn:
            self.conn = await aiosqlite.connect(self.db_name, timeout=10)
            await self.conn.execute("PRAGMA journal_mode=WAL;")
            await self.conn.execute("PRAGMA synchronous=NORMAL;")

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def _run(self, mode, q, p=(), r=3):
        if not self.conn:
            await self.connect()
        last_error = None
        for attempt in range(r):
            try:
                if mode == 'exec':
                    async with self.conn.execute(q, p) as c:
                        await self.conn.commit()
                        return c.rowcount
                elif mode == 'many':
                    await self.conn.executemany(q, p)
                    await self.conn.commit()
                    return
                elif mode == 'one':
                    async with self.conn.execute(q, p) as c:
                        return await c.fetchone()
                elif mode == 'all':
                    async with self.conn.execute(q, p) as c:
                        return await c.fetchall()
            except aiosqlite.OperationalError as e:
                last_error = e
                msg = str(e).lower()
                if "locked" not in msg and "busy" not in msg:
                    logging.error(f"DB {mode} failed: {e} | SQL: {q}")
                    raise
                if attempt == r - 1:
                    logging.error(f"DB {mode} retry exhausted: {e} | SQL: {q}")
                await asyncio.sleep(0.2)
        return 0 if mode == 'exec' else (None if mode == 'one' else [])

    async def execute(self, q, p=(), r=3): return await self._run('exec', q, p, r)
    async def executemany(self, q, p, r=3): return await self._run('many', q, p, r)
    async def fetchone(self, q, p=(), r=3): return await self._run('one', q, p, r)
    async def fetchall(self, q, p=(), r=3): return await self._run('all', q, p, r)

def has_permission(ctx):
    return (u := ctx.author.name.lower()) in BOT_ADMINS or ctx.author.is_mod or u == ctx.channel.name.lower()

def require_general_admin(func):
    @wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        if (u := ctx.author.name.lower()) != ctx.channel.name.lower() and u not in ALLOWED_USERS | BOT_ADMINS: return await ctx.send("⛔ 權限不足：此指令僅限台主或系統管理員使用。")
        try: return await func(self, ctx, *args, **kwargs)
        except Exception as e: logging.error(f"Cmd Error: {e}")
    return wrapper

def safe_command(func):
    @wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        try: return await func(self, ctx, *args, **kwargs)
        except Exception as e: logging.error(f"Cmd Error: {e}")
    return wrapper

# --- Selenium 驅動 ---
def get_selenium_driver():
    opts = Options()
    os.makedirs(CHROME_PROFILE_ROOT, exist_ok=True)
    profile_dir = os.path.join(CHROME_PROFILE_ROOT, f"bot_{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}")
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--mute-audio")
    opts.add_argument("window-size=1920,1080")
    opts.add_argument("--log-level=3")
    opts.add_argument(f"--user-data-dir={profile_dir}")

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-crash-reporter")

    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-default-apps")
    opts.add_argument("--disable-sync")
    opts.add_argument("--no-first-run")
    opts.add_argument("--hide-scrollbars")

    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--remote-debugging-port=0")

    # 🟢 加入安全啟動與無腦重試機制
    for attempt in range(3):
        service = Service(ChromeDriverManager().install())
        try:
            driver = webdriver.Chrome(service=service, options=opts)
            driver._bot_profile_dir = profile_dir
            driver._bot_driver_pid = service.process.pid if service.process else None
            return driver
        except Exception as e:
            # session 建立失敗時 chromedriver 子程序可能已啟動但沒有 driver 物件可回收，
            # 不手動收掉就會變成孤兒程序一直卡著
            if service.process:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(service.process.pid)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.rmtree(profile_dir, ignore_errors=True)
            if attempt < 2:
                # 啟動失敗常是殘留的 Chrome 殭屍程序佔住資源，先清一輪再重試
                force_cleanup_zombies()
                time.sleep(2)
                continue
            raise e

def _terminate_driver(driver):
    """強制結束 driver 對應的 chromedriver/Chrome 程序樹並清掉設定檔。
    斷線或換IP重啟時 driver.quit() 可能卡住或失敗，光靠它清不掉殭屍程序，
    所以額外用記下來的 chromedriver PID 做 taskkill /T 強制收掉整個子程序樹。"""
    pid = getattr(driver, "_bot_driver_pid", None)
    try:
        driver.quit()
    except Exception:
        pass
    if pid:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    profile_dir = getattr(driver, "_bot_profile_dir", None)
    if profile_dir:
        shutil.rmtree(profile_dir, ignore_errors=True)

# --- 全域輔助函數 ---
def force_cleanup_zombies():
    """只清理本 bot 建立的 headless Chrome profile，避免誤傷其他自動化工具。"""
    try:
        killed_any = False
        profile_marker = os.path.normcase(os.path.abspath(CHROME_PROFILE_ROOT)).replace("/", "\\")
        output = subprocess.check_output(
            'wmic process where "name=\'chrome.exe\'" get processid,commandline',
            shell=True,
            stderr=subprocess.DEVNULL
        ).decode('utf-8', errors='ignore')

        for line in output.splitlines():
            normalized = os.path.normcase(line).replace("/", "\\")
            if '--headless' in line and profile_marker in normalized:
                parts = line.strip().split()
                if parts and parts[-1].isdigit():
                    subprocess.run(["taskkill", "/f", "/pid", parts[-1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    killed_any = True

        if killed_any:
            time.sleep(1.0)

        if os.path.isdir(CHROME_PROFILE_ROOT):
            for name in os.listdir(CHROME_PROFILE_ROOT):
                path = os.path.join(CHROME_PROFILE_ROOT, name)
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                except Exception:
                    pass
    except Exception as e:
        logging.debug(f"Chrome cleanup skipped: {e}")

atexit.register(force_cleanup_zombies)


#===============================================================================
# [1] Bot 主程式
# ==============================================================================
class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token=TWITCH_IRC_TOKEN, prefix='!', initial_channels=[])
        self.db, self.client_id, self.access_token = Database(), CLIENT_ID, TWITCH_ACCESS_TOKEN
        self.user_access_token, self.user_refresh_token, self.session = LATEST_USER_TOKEN, LATEST_REFRESH_TOKEN, None
        self.bot_user_id, self.start_time, self.bot_version, self.current_ip = None, None, BOT_VERSION, None
        self.signin_disabled_channels, self.announce_disabled_channels, self.vip_batch = set(), set(), set()
        self.display_name_cache_ttl, self.broadcaster_name_map, self.chat_name_cache, self._user_cache, self.mod_cache = {}, {}, {}, {}, {}
        self.last_message_time, self.stream_start_times, self.live_status, self._silence_strikes = {}, {}, {}, {}
        self.zombie_check_pending, self.last_stream_ids, self.last_stream_dates = {}, {}, {}
        self._no_mod_channels = set()
        self.active_chatters = {}

        self.pending_proposals, self.pending_divorces, self.cooldowns = {}, {}, {}
        self.regular_queue = {}
        self.active_drivers: list = []
        self._donation_send_ts: dict = {}  # 斗內速率限制用時間戳

        self._mod_refresh_interval = 180
        self._val_cache = {}  # key: "rank:name#tag" / "matches:name#tag", value: (result_str, timestamp)
        self.token_lock, self.user_token_lock, self._background_tasks, self._tasks_started = asyncio.Lock(), asyncio.Lock(), set(), False
        self._background_task_factories, self._api_fail_since, self._api_fail_strikes = {}, None, 0
        self._last_offline_keepalive, self._ws_dead_strikes = 0, 0
        self._ws_unhealthy_since = None
        self.chat_app_access_token, self._chat_api_warned_channels = os.getenv("TWITCH_CHAT_APP_ACCESS_TOKEN"), set()
        self._last_chat_api_error = ""
        self._install_context_chat_api_patch()
        self.broadcaster_propose_replies, self.manual_nicknames = {"sweet_0530": "🚫 抱歉，大芯是惠惠寶貝的，不能娶走喔！"}, {"大芯喲": "sweet_0530", "大芯": "sweet_0530", "惠惠": "sweet_0530"}

    async def event_ready(self):
        if not getattr(self, "_is_first_login", False):
            self.bot_user_id = self.user_id
            logging.info(f"✅ 登入成功：{self.nick} (UID: {self.user_id})")
            self.start_time, self.session = self.start_time or datetime.datetime.now(LOCAL_TZ), self.session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
            await asyncio.gather(self._setup_database_env(), self._setup_twitch_env())

            if not self._tasks_started:
                self._tasks_started = True
                self._start_all_background_tasks()
                self.loop.create_task(self._delayed_donation_listeners())

            self._is_first_login = True
        else:
            logging.info(f"♻️聊天室連線瞬斷，已自動重新連線！")
            try: await self.join_channels(INITIAL_CHANNELS)
            except: pass

    async def _setup_database_env(self):
        await self.db.connect()
        logging.info("💾 資料庫已連線 (WAL Mode + Auto Flush)")
        await self.init_db()
        await self.check_and_update_schema()
        try:
            self.signin_disabled_channels = {r[0] for r in await self.db.fetchall("SELECT channel FROM channel_settings WHERE signin_enabled = 0")}
            self.announce_disabled_channels = {r[0] for r in await self.db.fetchall("SELECT channel FROM channel_settings WHERE announce_enabled = 0")}
        except Exception as e: logging.error(f"Settings Load Error: {e}")

    async def _setup_twitch_env(self):
        await self.refresh_token()
        await self.refresh_chat_app_token()
        await self.validate_token_scopes()
        self.current_ip = await self.get_public_ip()

        if INITIAL_CHANNELS:
            total = len(INITIAL_CHANNELS)
            mid = (total + 1) // 2
            part1 = INITIAL_CHANNELS[:mid]
            part2 = INITIAL_CHANNELS[mid:]

            logging.info(f"🔌 連線頻道: {' | '.join(part1)}")
            if part2:
                logging.info(f"           └─ {' | '.join(part2)}")

            try: await self.join_channels(INITIAL_CHANNELS)
            except Exception as e: logging.error(f"Join channels error: {e}")
            await self.cache_broadcaster_names(INITIAL_CHANNELS)

        if row := await self.db.fetchone("SELECT value FROM bot_state WHERE key='RESTART_CHANNEL'"):
            await self.db.execute("DELETE FROM bot_state WHERE key='RESTART_CHANNEL'")
            await asyncio.sleep(5)
            trigger = row[0].strip().lower()
            if not trigger.startswith("system_") and not trigger.startswith("auto_fix_"):
                await self.safe_channel_send(trigger, "🔁 Bot 已成功修復！ BloodTrail ")

    def _start_all_background_tasks(self):
        tasks = [
            self.health_watchdog_task, self.track_streams_task, self.monitor_chat_silence, self.daily_reset_task,
            self.monthly_reset_task, self.periodic_mod_refresh, self.announce_regular_task,
            self.monitor_ip_change, self.flush_vip_data_task,
            self.cleanup_cache_task, self.watch_time_tracker_task, self.update_rates_task
        ]
        for t in tasks:
            self._spawn_background_task(t.__name__, t)

    def _spawn_background_task(self, name, factory):
        self._background_task_factories[name] = factory
        task = self.loop.create_task(factory())
        self._background_tasks.add(task)
        task.add_done_callback(lambda done, task_name=name: self._handle_background_task_done(task_name, done))

    def _handle_background_task_done(self, name, task):
        self._background_tasks.discard(task)
        if getattr(self, "_restarting", False) or task.cancelled():
            return
        exc = task.exception()
        if exc:
            logging.error(f"💥 背景任務 {name} 意外停止：{exc}")
        else:
            logging.warning(f"⚠️ 背景任務 {name} 已結束，準備重啟。")
        factory = self._background_task_factories.get(name)
        if factory:
            self.loop.call_later(5, lambda: self._spawn_background_task(name, factory))


    # ==============================================================================
    # [斗內監聽系統]
    # ==============================================================================
    async def _delayed_donation_listeners(self):
        logging.info("⏳ 系統已上線[多頻道獨立斗內監聽]...")
        await asyncio.sleep(15)

        channels_to_check = set([c.strip().lower() for c in INITIAL_CHANNELS + [self.nick.lower()]])

        for ch in channels_to_check:
            launched_any = False

            url_opay = os.getenv(f'URL_OPAY_{ch}', '').strip() or URL_OPAY.strip()
            opay_status = "🟢" if (ENABLE_OPAY and url_opay) else "🔴"
            if opay_status == "🟢":
                threading.Thread(target=self.run_alert_listener, args=(ch, url_opay, "歐富寶", "DinoDance  (OPay)"), daemon=True).start()
                launched_any = True
                await asyncio.sleep(4)

            url_ecpay = os.getenv(f'URL_ECPAY_{ch}', '').strip() or URL_ECPAY.strip()
            ecpay_status = "🟢" if (ENABLE_ECPAY and url_ecpay) else "🔴"
            if ecpay_status == "🟢":
                threading.Thread(target=self.run_alert_listener, args=(ch, url_ecpay, "綠界", "HolidayPresent (ECPay)"), daemon=True).start()
                launched_any = True
                await asyncio.sleep(4)

            url_paypal = os.getenv(f'URL_PAYPAL_{ch}', '').strip() or URL_PAYPAL.strip()
            paypal_status = "🟢" if (ENABLE_PAYPAL and url_paypal) else "🔴"
            if paypal_status == "🟢":
                threading.Thread(target=self.run_paypal, args=(ch, url_paypal), daemon=True).start()
                launched_any = True
                await asyncio.sleep(4)

            if "🟢" in [opay_status, ecpay_status, paypal_status]:
                status_bar = f"[歐富寶:{opay_status}|綠界:{ecpay_status}|PayPal:{paypal_status}]"
                logging.info(f"🎧 啟動[{ch}]監聽狀態{status_bar}")
                if launched_any: await asyncio.sleep(3)

    def safe_send_message(self, msg, specific_channel=None, log_text=None, donation_event_key=None):
        # 🛡️ 智能座標替換引擎 (保護無辜字，只炸觸發字)
        def smart_replacer(match):
            text = match.group(0)
            result = ""
            last_end = 0

            last_idx = match.lastindex or 0
            for i in range(1, last_idx + 1):
                if match.group(i) is None: continue
                start = match.span(i)[0] - match.span(0)[0]
                end = match.span(i)[1] - match.span(0)[0]
                bad_len = start - last_end
                if bad_len > 0: result += "*" * bad_len
                result += text[start:end]
                last_end = end

            bad_len = len(text) - last_end
            if bad_len > 0: result += "*" * bad_len
            return result

        def protected_spans(text):
            spans = []
            for emote in PROTECTED_TWITCH_EMOTES:
                pattern = rf"(?<![A-Za-z0-9_]){re.escape(emote)}(?![A-Za-z0-9_])"
                spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text))

            money_patterns = [
                r"(?<=斗內\s)(?:NT\$|[$€£¥]|USD|EUR|GBP|JPY|KRW|TWD)?\s*\d[\d,]*(?:\.\d+)?(?=\s*元[：:])",
                r"(?<![A-Za-z0-9_])(?:NT\$|[$€£¥]|USD|EUR|GBP|JPY|KRW|TWD)\s*\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9_])",
                r"(?<![A-Za-z0-9_])\d[\d,]*(?:\.\d+)?\s*(?:元|TWD|USD|EUR|GBP|JPY|KRW)(?![A-Za-z0-9_])",
            ]
            for pattern in money_patterns:
                spans.extend((m.start(), m.end()) for m in re.finditer(pattern, text, flags=re.IGNORECASE))

            if not spans:
                return []

            spans.sort()
            merged = [spans[0]]
            for start, end in spans[1:]:
                last_start, last_end = merged[-1]
                if start <= last_end:
                    merged[-1] = (last_start, max(last_end, end))
                else:
                    merged.append((start, end))
            return merged

        def censor_segment(segment):
            # --- 1. 處理第一層：正則表達式 ---
            for p in STRICT_PATTERNS:
                if not p: continue
                try: segment = re.sub(p, smart_replacer, segment, flags=re.IGNORECASE)
                except: pass

            # --- 2. 處理第二層：常規黑名單 ---
            for bad_word in BANNED_WORDS:
                bad_word = bad_word.strip()
                if not bad_word or bad_word.startswith('#'): continue
                chars = list(bad_word)
                pattern = r'(.*?)'.join(re.escape(c) for c in chars)
                try: segment = re.sub(pattern, smart_replacer, segment, flags=re.IGNORECASE)
                except: pass
            return segment

        protected = protected_spans(msg)
        if protected:
            parts, pos = [], 0
            for start, end in protected:
                if pos < start:
                    parts.append(censor_segment(msg[pos:start]))
                parts.append(msg[start:end])
                pos = end
            if pos < len(msg):
                parts.append(censor_segment(msg[pos:]))
            msg = "".join(parts)
        else:
            msg = censor_segment(msg)

        # === 輕量級發送與「100% 真實確認」邏輯 ===
        targets = [specific_channel.lower()] if specific_channel else (DONATION_TARGET_CHANNELS if DONATION_TARGET_CHANNELS else [self.nick.lower()])
        for channel_name in targets:
            ch = self.get_channel(channel_name)

            # 如果找不到目標頻道，退回機器人本台
            if not ch:
                channel_name = self.nick.lower()
                ch = self.get_channel(channel_name)

            if ch:
                # 🛡️ 速率保護：同一頻道斗內訊息最短 2 秒間隔，避免打爆 Twitch 速率限制
                _now = time.time()
                _gap = _now - self._donation_send_ts.get(channel_name, 0)
                if _gap < 2.0:
                    time.sleep(2.0 - _gap)
                self._donation_send_ts[channel_name] = time.time()

                # 🟢 建立一個非同步確認任務
                async def _send_and_confirm(target_ch, message, confirm_log):
                    try:
                        send_mode = await self._send_donation_chat_message(target_ch, message)
                        if send_mode:
                            if donation_event_key:
                                await self.mark_donation_sent(donation_event_key, "sent")
                            if confirm_log:
                                logging.info(f"{confirm_log} 已透過 {send_mode} 發送成功！")
                            else:
                                logging.info(f"✅ 已透過 {send_mode} 成功發送至 [{target_ch}] 聊天室！")
                        else:
                            if donation_event_key:
                                await self.mark_donation_sent(donation_event_key, "failed")
                            logging.error(f"❌ 斗內發送至 [{target_ch}] 失敗")
                    except Exception as e:
                        if donation_event_key:
                            await self.mark_donation_sent(donation_event_key, "failed")
                        logging.error(f"❌ 斗內發送至 [{target_ch}] 失敗: {e}")

                # 丟給背景執行
                asyncio.run_coroutine_threadsafe(_send_and_confirm(channel_name, msg, log_text), self.loop)
            else:
                logging.error(f"❌ 嚴重錯誤：連機器人自己的頻道 ({self.nick}) 都無法連線！")


    def extract_donation_amount_text(self, text):
        if not text:
            return ""
        m = re.search(r'(?:NT\$|TWD|USD|EUR|GBP|JPY|KRW|[$€£¥])?\s*\d+(?:,\d{3})*(?:\.\d+)?', text, re.IGNORECASE)
        return m.group(0).strip() if m else ""

    def parse_donation_amount(self, amount_text):
        if not amount_text:
            return None, "TWD"

        symbol_map = {
            "$": "USD", "NT$": "TWD", "TWD": "TWD",
            "USD": "USD", "€": "EUR", "EUR": "EUR",
            "£": "GBP", "GBP": "GBP", "¥": "JPY",
            "JPY": "JPY", "KRW": "KRW"
        }
        currency = "TWD"
        raw = amount_text.strip()
        prefix = re.match(r'^(NT\$|TWD|USD|EUR|GBP|JPY|KRW|[$€£¥])', raw, re.IGNORECASE)
        if prefix:
            currency = symbol_map.get(prefix.group(1).upper(), symbol_map.get(prefix.group(1), "TWD"))

        m = re.search(r'\d+(?:,\d{3})*(?:\.\d+)?', raw)
        if not m:
            return None, currency
        try:
            return float(m.group(0).replace(",", "")), currency
        except ValueError:
            return None, currency

    def build_donation_event_key(self, channel, platform, donor_name, amount_text, message, raw_text):
        # Alert boxes do not expose a stable donation id, so every detected donation gets
        # its own key. This keeps the database as a full event log, not a dedupe gate.
        base = "\n".join([
            channel.strip().lower(),
            platform.strip().lower(),
            donor_name.strip().lower(),
            amount_text.strip(),
            re.sub(r'\s+', ' ', message.strip()),
            re.sub(r'\s+', ' ', raw_text.strip()),
            str(time.time_ns()),
        ])
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    async def record_donation_event(self, channel, platform, donor_name, amount_text, message, raw_text):
        amount_value, currency = self.parse_donation_amount(amount_text)
        event_key = self.build_donation_event_key(channel, platform, donor_name, amount_text, message, raw_text)
        detected_at = datetime.datetime.now(LOCAL_TZ).isoformat()
        await self.db.execute(
            "INSERT INTO donation_events "
            "(event_key, channel, platform, donor_name, amount_text, amount_value, currency, message, raw_text, detected_at, send_status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_key, channel, platform, donor_name, amount_text, amount_value, currency, message, raw_text, detected_at, "pending")
        )
        return event_key

    async def mark_donation_sent(self, event_key, status):
        sent_at = datetime.datetime.now(LOCAL_TZ).isoformat() if status == "sent" else None
        await self.db.execute("UPDATE donation_events SET send_status=?, sent_at=? WHERE event_key=?", (status, sent_at, event_key))

    def submit_donation_event(self, target_channel, platform_name, donor_name, amount_text, message, raw_text, chat_message, log_text):
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.record_donation_event(target_channel, platform_name, donor_name, amount_text, message, raw_text),
                self.loop
            )
            event_key = future.result(timeout=10)
        except Exception as e:
            logging.error(f"❌ [{target_channel} {platform_name}] 斗內寫入資料庫失敗，已取消發送：{e}")
            return

        self.safe_send_message(chat_message, specific_channel=target_channel, log_text=log_text, donation_event_key=event_key)

    def run_alert_listener(self, target_channel, url, platform_name, suffix_str):
        while True:
            driver = None
            try:
                driver = get_selenium_driver()
                self.active_drivers.append(driver)
                driver.get(url)
                last = ""
                refresh_counter = 0

                while True:
                    try:
                        box = driver.find_element(By.ID, "alert_container")
                        if "hide" not in box.get_attribute("class"):
                            name, amt, msg = "", "", ""
                            for _ in range(15):
                                try:
                                    get_txt = lambda id: driver.find_element(By.ID, id).text.replace("\n", "").strip()
                                    n, a = get_txt("name"), get_txt("amount")
                                    if n and a:
                                        name, amt, msg = n, a, get_txt("content")
                                        break
                                except: pass
                                time.sleep(0.3)

                            full = f"{name}|{amt}|{msg}"
                            if name and amt and full != last:
                                info_log = f"💰 [{target_channel} {platform_name}] {name} 斗內 {amt}"
                                chat_message = f" GoldPLZ 感謝 {name} 斗內 {amt} 元：{msg} {suffix_str}"
                                self.submit_donation_event(target_channel, platform_name, name, amt, msg, full, chat_message, info_log)
                                last = full
                                time.sleep(12)
                        else:
                            if last:
                                last = ""
                    except Exception:
                        pass

                    refresh_counter += 1
                    if refresh_counter > 40000:
                        logging.debug(f"🔄 [{target_channel} {platform_name}] 執行定時網頁重整以釋放記憶體")
                        driver.refresh()
                        refresh_counter = 0
                        time.sleep(5)

                    time.sleep(0.5)
            except Exception as e:
                logging.error(f"⚠️ [{target_channel} {platform_name}] 監聽器發生異常，10 秒後重啟: {e}")
                force_cleanup_zombies()
                time.sleep(10)
            finally:
                if driver:
                    _terminate_driver(driver)
                    try: self.active_drivers.remove(driver)
                    except ValueError: pass

    def run_paypal(self, target_channel, url):
        while True:
            driver = None
            try:
                driver = get_selenium_driver()
                self.active_drivers.append(driver)
                driver.get(url)
                last = ""
                refresh_counter = 0

                while True:
                    current_text = ""
                    try: current_text = driver.find_element(By.TAG_NAME, 'body').text.strip()
                    except: pass

                    if not current_text:
                        iframes = driver.find_elements(By.TAG_NAME, "iframe")
                        for iframe in iframes:
                            try:
                                driver.switch_to.frame(iframe)
                                txt = driver.find_element(By.TAG_NAME, 'body').text.strip()
                                if txt: current_text = txt
                                driver.switch_to.default_content()
                            except:
                                driver.switch_to.default_content()

                    if current_text and current_text != last:
                        # 🛡️ 收緊匹配：需同時有貨幣符號 + 緊接數字，且文字夠長才視為真實斗內
                        is_donation = (
                            len(current_text) >= 10 and
                            re.search(r'([$€£¥]|USD|EUR|GBP|JPY|KRW|TWD|NT\$)\s?\d', current_text, re.IGNORECASE)
                        )
                        if is_donation:
                            info_log = f"💰 [{target_channel} PayPal] 偵測到斗內: {current_text}"
                            amount_text = self.extract_donation_amount_text(current_text)
                            chat_message = f" GoldPLZ 感謝斗內！ {self.convert_twd(current_text)} GlitchCat (PayPal)"
                            self.submit_donation_event(target_channel, "PayPal", "", amount_text, current_text, current_text, chat_message, info_log)
                        else:
                            logging.debug(f"🔍 [{target_channel} PayPal] 忽略非斗內文字變動: {current_text[:30]}")
                        last = current_text

                    if not current_text:
                        last = ""

                    refresh_counter += 1
                    if refresh_counter > 40000:
                        driver.refresh()
                        refresh_counter = 0
                        time.sleep(5)

                    time.sleep(0.5)
            except Exception as e:
                logging.error(f"⚠️ [{target_channel} PayPal] 監聽器發生異常，10 秒後重啟: {e}")
                force_cleanup_zombies()
                time.sleep(10)
            finally:
                if driver:
                    _terminate_driver(driver)
                    try: self.active_drivers.remove(driver)
                    except ValueError: pass

    def convert_twd(self, text):
        try:
            m = re.search(r'([$€£¥]|USD|EUR|GBP|JPY|KRW)\s?(\d+(?:,\d{3})*(?:\.\d+)?)', text)
            if m and (rate := RATES.get(m.group(1))):
                twd = int(float(m.group(2).replace(',', '')) * rate)
                return f"{text} (約 NT${twd})"
        except: pass
        return text

    async def update_rates_task(self):
        while True:
            try:
                async with self.session.get('https://tw.rter.info/capi.php') as r:
                    data = await r.json()
                    usd = data['USDTWD']['Exrate']
                    RATES['USD'], RATES['$'] = usd, usd
                    RATES['JPY'], RATES['¥'] = usd / data['USDJPY']['Exrate'], usd / data['USDJPY']['Exrate']
                    RATES['EUR'], RATES['€'] = usd / data['USDEUR']['Exrate'], usd / data['USDEUR']['Exrate']
                    RATES['GBP'], RATES['£'] = usd / data['USDGBP']['Exrate'], usd / data['USDGBP']['Exrate']
                    RATES['KRW'] = usd / data['USDKRW']['Exrate']
            except: pass
            await asyncio.sleep(1800)

    # ==============================================================================
    # [核心系統與退出]
    # ==============================================================================
    async def _graceful_shutdown(self):
        if self.vip_batch:
            data = [(d[0], d[1], d[2], d[3], d[1], d[3]) for d in list(self.vip_batch)]; self.vip_batch.clear()
            try:
                await self.db.executemany(
                    "INSERT INTO known_vips (user_id, user_login, channel, last_seen) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(user_id, channel) DO UPDATE SET user_login=?, last_seen=?",
                    data,
                )
            except: pass

        if self.session: await self.session.close()
        await self.db.close()

        logging.info("🧹 正在清理背景瀏覽器資源...")
        if hasattr(self, "active_drivers"):
            for driver in self.active_drivers:
                _terminate_driver(driver)
            self.active_drivers.clear()
        # os.execv 不會觸發 atexit，斷線/換IP重啟前在這裡多掃一輪，避免殭屍程序累積
        force_cleanup_zombies()

    async def close(self):
        await self._graceful_shutdown()
        try: await super().close()
        except: pass

    async def hard_restart(self, trigger_channel, is_manual=False):
        if getattr(self, "_restarting", False): return
        self._restarting = True
        logging.error(f"💥 執行全域重啟 (Trigger: {trigger_channel}, Manual: {is_manual}) - 系統即將重新啟動")

        if is_manual:
            try: await self.safe_channel_send(trigger_channel, "⚠️ 系統正在手動重新啟動以套用設定...")
            except: pass
            await self.db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", ("RESTART_CHANNEL", trigger_channel.lower()))
        else:
            await self.db.execute("DELETE FROM bot_state WHERE key='RESTART_CHANNEL'")

        await self._graceful_shutdown()
        await asyncio.sleep(2)
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # ==============================================================================
    # [2] 資料庫初始化區
    # ==============================================================================
    async def init_db(self):
        tables = [
            '''CREATE TABLE IF NOT EXISTS checkins (
                user_id TEXT, user TEXT, display_name TEXT, channel TEXT,
                count INTEGER, last_checkin TEXT,
                total_count INTEGER DEFAULT 0, monthly_count INTEGER DEFAULT 0,
                last_stream_id TEXT, last_checkin_ts INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, channel))''',
            '''CREATE TABLE IF NOT EXISTS channel_stats (
                channel TEXT PRIMARY KEY, stream_count INTEGER DEFAULT 0)''',
            '''CREATE TABLE IF NOT EXISTS monthly_top5 (
                channel TEXT, month TEXT, rank INTEGER,
                user TEXT, display_name TEXT, count INTEGER,
                PRIMARY KEY (channel, month, rank))''',
            'CREATE TABLE IF NOT EXISTS bot_state (key TEXT PRIMARY KEY, value TEXT)',
            '''CREATE TABLE IF NOT EXISTS known_vips (
                user_id TEXT, user_login TEXT, channel TEXT, last_seen TEXT,
                PRIMARY KEY (user_id, channel))''',
            '''CREATE TABLE IF NOT EXISTS marriages (
                user1_id TEXT, user1_name TEXT, user2_id TEXT, user2_name TEXT,
                channel TEXT, marriage_date TEXT,
                PRIMARY KEY (user1_id, user2_id, channel))''',
            '''CREATE TABLE IF NOT EXISTS channel_settings (
                channel TEXT PRIMARY KEY,
                signin_enabled INTEGER DEFAULT 1,
                announce_enabled INTEGER DEFAULT 1)''',
            '''CREATE TABLE IF NOT EXISTS user_aliases (
                user_id TEXT, display_name TEXT, last_seen TEXT,
                PRIMARY KEY (user_id, display_name))''',
            '''CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT DEFAULT "global",
                content TEXT, added_at TEXT, added_by TEXT,
                is_session_only INTEGER DEFAULT 0)''',
            '''CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT, channel TEXT,
                is_online INTEGER DEFAULT 0,
                last_entry_ts INTEGER DEFAULT 0, last_leave_ts INTEGER DEFAULT 0,
                watch_minutes REAL DEFAULT 0, message_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, channel))''',
            '''CREATE TABLE IF NOT EXISTS val_bindings (
                user_id TEXT PRIMARY KEY, riot_id TEXT, bound_at TEXT)''',
            '''CREATE TABLE IF NOT EXISTS donation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT UNIQUE, channel TEXT, platform TEXT,
                donor_name TEXT, amount_text TEXT, amount_value REAL,
                currency TEXT, message TEXT, raw_text TEXT,
                detected_at TEXT, sent_at TEXT,
                send_status TEXT DEFAULT "pending")''',
            'CREATE INDEX IF NOT EXISTS idx_checkins_user_id ON checkins (user_id)',
            'CREATE INDEX IF NOT EXISTS idx_user_aliases_user_id ON user_aliases (user_id)',
            'CREATE INDEX IF NOT EXISTS idx_marriages_u1 ON marriages (user1_id, channel)',
            'CREATE INDEX IF NOT EXISTS idx_marriages_u2 ON marriages (user2_id, channel)',
            'CREATE INDEX IF NOT EXISTS idx_donation_events_channel_time ON donation_events (channel, detected_at)',
            'CREATE INDEX IF NOT EXISTS idx_donation_events_event_key ON donation_events (event_key)',
        ]
        for s in tables:
            await self.db.execute(s)

    async def check_and_update_schema(self):
        try:
            ex_cols_cs = [r[1] for r in await self.db.fetchall("PRAGMA table_info(channel_settings)")]
            for c, d in {"signin_enabled": "INTEGER DEFAULT 1", "announce_enabled": "INTEGER DEFAULT 1"}.items():
                if c not in ex_cols_cs: await self.db.execute(f"ALTER TABLE channel_settings ADD COLUMN {c} {d}")
            ex_cols_ci = [r[1] for r in await self.db.fetchall("PRAGMA table_info(checkins)")]
            if "last_checkin_ts" not in ex_cols_ci:
                await self.db.execute("ALTER TABLE checkins ADD COLUMN last_checkin_ts INTEGER DEFAULT 0")

            ex_cols_ann = [r[1] for r in await self.db.fetchall("PRAGMA table_info(announcements)")]
            if "is_session_only" not in ex_cols_ann:
                await self.db.execute("ALTER TABLE announcements ADD COLUMN is_session_only INTEGER DEFAULT 0")
            if "channel" not in ex_cols_ann:
                await self.db.execute("ALTER TABLE announcements ADD COLUMN channel TEXT DEFAULT 'global'")
                if INITIAL_CHANNELS:
                    await self.db.execute("UPDATE announcements SET channel = ?", (INITIAL_CHANNELS[0],))
        except Exception as e: logging.error(f"Schema Error: {e}")

    # ==============================================================================
    # [3] 時間與字串工具區
    # ==============================================================================
    def format_time_ago(self, ts): return "未知" if not ts else (f"{d}秒前" if (d := int(time.time()) - ts) < 60 else f"{d//60}分鐘前" if d < 3600 else f"{d//3600}小時前" if d < 86400 else f"{d//86400}天前")
    def format_watch_time(self, mins):
        h, m = divmod(int(mins), 60)
        d, h = divmod(h, 24)
        return f"{d}天{h}時{m}分" if d else f"{h}時{m}分" if h else f"{m}分"
    def format_hhmm(self, ts): return datetime.datetime.fromtimestamp(ts, LOCAL_TZ).strftime("%H:%M") if ts else "未知"
    def format_uptime_digital(self, st):
        d = datetime.datetime.now(st.tzinfo) - st; h, r = divmod(d.seconds, 3600); m, s = divmod(r, 60)
        return f"{d.days}d {h:02}:{m:02}:{s:02}" if d.days else f"{h:02}:{m:02}:{s:02}"
    def format_duration_zh(self, dt):
        d = relativedelta(datetime.datetime.now(datetime.timezone.utc), dt); p = ([f"{d.years}年"] if d.years else []) + ([f"{d.months}個月"] if d.months else []) + ([f"{d.days}天"] if d.days else [])
        return "".join(p) or "今天"
    def mask_ip(self, ip): return f"{ip.split('.')[0]}.{ip.split('.')[1]}.***.***" if ip and len(ip.split('.')) == 4 else "Unknown"

    # ==============================================================================
    # [4] Twitch API 封裝區
    # ==============================================================================
    async def cache_broadcaster_names(self, channels):
        try:
            async with self.session.get(f"https://api.twitch.tv/helix/users?{'&'.join([f'login={c}' for c in list(set(channels))[:100]])}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as res:
                if res.status == 200:
                    for u in (await res.json()).get("data", []): self.broadcaster_name_map[u["display_name"]] = self.broadcaster_name_map[u["login"].lower()] = (u["id"], u["login"], u["display_name"])
        except Exception as e: logging.error(f"Cache Broadcasters Error: {e}")

    async def fetch_stream_data(self, ch, retry=0):
        try:
            async with self.session.get(f"https://api.twitch.tv/helix/streams?user_login={ch}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as res:
                if res.status == 401:
                    if retry >= 1: return None
                    await self.refresh_token()
                    return await self.fetch_stream_data(ch, retry=1)
                if res.status != 200:
                    self._api_fail_strikes = getattr(self, '_api_fail_strikes', 0) + 1
                    if self._api_fail_since is None:
                        self._api_fail_since = time.time()
                    if self._api_fail_strikes == 1 or self._api_fail_strikes % 10 == 0:
                        logging.warning(f"⚠️ Twitch API 暫時異常 ({res.status})，保留原本直播狀態。")
                    return None
                self._api_fail_strikes = 0
                self._api_fail_since = None
                return (await res.json()).get("data", [])
        except Exception as e:
            self._api_fail_strikes = getattr(self, '_api_fail_strikes', 0) + 1
            if self._api_fail_since is None:
                self._api_fail_since = time.time()
            if self._api_fail_strikes == 1:
                logging.error(f"⚠️ 無法連線至 Twitch API，靜默等待恢復... [{e}]")
            return None

    async def is_live(self, ch): return bool(await self.fetch_stream_data(ch))

    async def fetch_display_names_from_api(self, users):
        now_ts, uncached = time.time(), [u for u in users if u not in self.display_name_cache_ttl or now_ts - self.display_name_cache_ttl[u][0] > 300]
        if uncached:
            try:
                for chunk in [uncached[i:i+100] for i in range(0, len(uncached), 100)]:
                    async with self.session.get(f"https://api.twitch.tv/helix/users?{'&'.join(f'login={u}' for u in chunk)}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as res:
                        if res.status == 200:
                            for u in (await res.json()).get("data", []): self.display_name_cache_ttl[u["login"].lower()] = (now_ts, u["display_name"])
                    await asyncio.sleep(0.1)
            except Exception as e: logging.error(f"fetch_display_names error: {e}")
        return {u: self.display_name_cache_ttl.get(u, (now_ts, u))[1] for u in users}

    async def get_smart_user(self, target_str):
        if not target_str: return None
        target_str = target_str.replace("@", "").strip(); t_lower = target_str.lower()
        if target_str in self.manual_nicknames and (uid := await self._get_user_id_by_login(self.manual_nicknames[target_str])): return str(uid), self.manual_nicknames[target_str], self.display_name_cache_ttl.get(self.manual_nicknames[target_str], (0, target_str))[1]
        if target_str.isdigit() and (u := next(iter(await self.fetch_users(ids=[int(target_str)]) or []), None)): self._user_cache[u.name.lower()] = str(u.id); return str(u.id), u.name.lower(), u.display_name
        if target_str in self.chat_name_cache: return self.chat_name_cache[target_str]
        if target_str in self.broadcaster_name_map: return self.broadcaster_name_map[target_str]
        try:
            async with self.session.get(f"https://api.twitch.tv/helix/users?login={t_lower}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as res:
                if res.status == 200 and (d := (await res.json()).get("data")): self._user_cache[d[0]["login"]] = d[0]["id"]; return d[0]["id"], d[0]["login"], d[0]["display_name"]
        except: pass
        if u := next(iter(await self.fetch_users(names=[target_str]) or []), None): self._user_cache[u.name.lower()] = str(u.id); return str(u.id), u.name.lower(), u.display_name
        if row := await self.db.fetchone("SELECT user_id, user, display_name FROM checkins WHERE display_name = ? LIMIT 1", (target_str,)): return row
        if row_alias := await self.db.fetchone("SELECT user_id FROM user_aliases WHERE display_name = ? LIMIT 1", (target_str,)):
            uid = row_alias[0]
            if r := await self.db.fetchone("SELECT user, display_name FROM checkins WHERE user_id=? LIMIT 1", (uid,)):
                return (uid, r[0], r[1])
            # checkins 沒有紀錄時，嘗試 Twitch API 取得真實 login
            try:
                async with self.session.get(f"https://api.twitch.tv/helix/users?id={uid}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as _r:
                    if _r.status == 200 and (d := (await _r.json()).get("data")):
                        self._user_cache[d[0]["login"]] = d[0]["id"]
                        return (uid, d[0]["login"], d[0]["display_name"])
            except: pass
            return (uid, target_str.lower(), target_str)  # 最後手段，用顯示名小寫當 login
        return None

    async def _get_user_id_by_login(self, login):
        if (login := login.lower()) in self._user_cache: return self._user_cache[login]
        try:
            async with self.session.get(f"https://api.twitch.tv/helix/users?login={login}", headers={"Client-ID": self.client_id, "Authorization": f"Bearer {self.access_token}"}) as res:
                if d := (await res.json()).get("data"): self._user_cache[login] = d[0]["id"]; return d[0]["id"]
        except: pass
        return None

    async def fetch_channel_moderators(self, ch):
        if not (bid := await self._get_user_id_by_login(ch)): return []
        try:
            async with self.session.get(f"https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={bid}", headers={"Authorization": f"Bearer {self.user_access_token or self.access_token}", "Client-Id": self.client_id}) as r: return [m["user_login"] for m in (await r.json()).get("data", [])] if r.status == 200 else []
        except: return []

    async def _moderation_api(self, method, ch, tgt_id, sec=None, reason=""):
        mod_id = getattr(self, "token_owner_id", None) or getattr(self, "bot_user_id", self.user_id)
        if not (bid := await self._get_user_id_by_login(ch)) or not tgt_id or not mod_id: return False, "ID 無效"
        headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {self.user_access_token}"}
        base_url = f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={bid}&moderator_id={mod_id}"
        if method == "POST":
            req_url = base_url
            kwargs = {"json": {"data": {"user_id": tgt_id, "duration": int(sec), "reason": reason[:500]}}}
            headers["Content-Type"] = "application/json"
        else:
            req_url = f"{base_url}&user_id={tgt_id}"
            kwargs = {}
        try:
            async with getattr(self.session, method.lower())(req_url, headers=headers, **kwargs) as r:
                if r.status == 401 and await self.refresh_user_token():
                    headers["Authorization"] = f"Bearer {self.user_access_token}"
                    async with getattr(self.session, method.lower())(req_url, headers=headers, **kwargs) as r2:
                        status, text = r2.status, await r2.text()
                else:
                    status, text = r.status, await r.text()

                if status in (200, 201, 204): return True, "成功"
                if status == 400 and method == "DELETE" and "not banned" in text.lower(): return False, "該觀眾目前並未被禁言"

                try: err_msg = json.loads(text).get("message", text)
                except: err_msg = text

                # 🟢 將 Twitch 錯誤轉為白話文，並隱藏 API 狀態碼
                if "may not be banned" in err_msg:
                    return False, "對方是管理員"

                return False, f"API {status}: {err_msg}"
        except Exception as e: return False, str(e)

    async def _unban_via_api(self, ch, tid): return await self._moderation_api("DELETE", ch, tid)
    async def _timeout_via_api(self, ch, tid, sec, r=""): return await self._moderation_api("POST", ch, tid, sec, r)

    async def resolve_target(self, ctx, target: str):
        target_clean = target.strip().replace("@", "") if target else ctx.author.name
        try:
            user_info = await self.get_smart_user(target_clean)
        except Exception:
            user_info = None
        if user_info: return user_info[0], user_info[1], user_info[2]
        if not target: return str(ctx.author.id), ctx.author.name.lower(), ctx.author.display_name
        return None, None, None

    async def _verify_custom_cmd_req(self, ctx, cmd_name: str = None):
        if not has_permission(ctx): return False, None, None
        ch = ctx.channel.name.lower()
        clean_cmd = cmd_name.replace("!", "").lower() if cmd_name else None
        return True, ch, clean_cmd

    async def _bot_can_announce_in_channel(self, channel_name: str) -> bool | None:
        ch = (channel_name or "").lower()
        bot_login = (getattr(self, "nick", "") or "").lower()
        if not ch or not bot_login:
            return False
        if ch == bot_login:
            return True
        if ch in getattr(self, "_no_mod_channels", set()):
            return False

        cached_mods = self.mod_cache.get(ch)
        if cached_mods is not None:
            return bot_login in cached_mods if cached_mods else None

        mods = [m.lower() for m in await self.fetch_channel_moderators(ch)]
        if mods:
            self.mod_cache[ch] = mods
            return bot_login in mods
        return None

    async def _send_donation_chat_message(self, channel_name: str, message: str):
        can_announce = await self._bot_can_announce_in_channel(channel_name)
        if can_announce is not False:
            if await self._send_api_announce(channel_name, message, color="orange", fallback=False):
                return "公告"
            if can_announce:
                logging.warning(f"⚠️ 斗內公告發送失敗 [{channel_name}]，改用一般聊天訊息。")
        else:
            logging.debug(f"ℹ️ BOT 不是 {channel_name} 的 MOD，斗內訊息改用一般聊天訊息。")

        return "聊天" if await self.send_chat_message(channel_name, message) else None

    async def _send_api_announce(self, channel_name: str, message: str, color: str = "primary", fallback: bool = True):
        """
        🟢 官方公告 API 模組 (自動降級機制)
        """
        message = message[:499]  # Twitch 公告 API 上限 500 字
        bid = await self._get_user_id_by_login(channel_name)
        mid = getattr(self, "bot_user_id", self.user_id)
        fallback_needed = False

        if bid and mid:
            url = f"https://api.twitch.tv/helix/chat/announcements?broadcaster_id={bid}&moderator_id={mid}"
            headers = {"Authorization": f"Bearer {self.user_access_token}", "Client-Id": self.client_id, "Content-Type": "application/json"}
            payload = {"message": message, "color": color}
            try:
                async with self.session.post(url, headers=headers, json=payload) as r:
                    if r.status == 204: return True
                    if r.status == 401 and await self.refresh_user_token():
                        headers["Authorization"] = f"Bearer {self.user_access_token}"
                        async with self.session.post(url, headers=headers, json=payload) as r2:
                            if r2.status == 204: return True
                    fallback_needed = True
            except: fallback_needed = True
        else:
            fallback_needed = True

        if fallback_needed:
            if not fallback:
                return False
            ch = self.get_channel(channel_name)
            if ch:
                try:
                    await ch.send(message)
                except Exception as e:
                    logging.error(f"❌ 公告降級發送失敗 [{channel_name}]: {e}")
            return False

    def _extract_message_id(self, message):
        if not message:
            return None
        if getattr(message, "id", None):
            return str(message.id)
        tags = getattr(message, "tags", None) or {}
        return tags.get("id") or tags.get("tmi-sent-ts")

    async def refresh_chat_app_token(self):
        try:
            async with self.session.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": CHAT_MESSAGE_API_SCOPE,
                },
            ) as r:
                if r.status == 200 and (d := await r.json()).get("access_token"):
                    self.chat_app_access_token = d["access_token"]
                    return True
                logging.warning(f"⚠️ 無法取得聊天徽章用 App Token (HTTP {r.status})")
        except Exception as e:
            logging.warning(f"⚠️ 無法取得聊天徽章用 App Token：{e}")
        return False

    async def _send_chat_message_api(self, channel_name: str, message: str, reply_parent_message_id: str = None, retry: bool = True):
        token = self.chat_app_access_token or self.access_token
        bid = await self._get_user_id_by_login(channel_name)
        sender_id = str(getattr(self, "bot_user_id", None) or getattr(self, "user_id", ""))
        if not token or not bid or not sender_id:
            self._last_chat_api_error = "缺少 token、頻道 ID 或 BOT sender_id"
            return False

        payload = {
            "broadcaster_id": str(bid),
            "sender_id": sender_id,
            "message": message[:500],
            "for_source_only": True,
        }
        if reply_parent_message_id:
            payload["reply_parent_message_id"] = str(reply_parent_message_id)

        headers = {
            "Authorization": f"Bearer {token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }

        try:
            async with self.session.post("https://api.twitch.tv/helix/chat/messages", headers=headers, json=payload) as r:
                data = await r.json(content_type=None) if r.content_type == "application/json" else {}
                if r.status == 401 and retry and await self.refresh_chat_app_token():
                    return await self._send_chat_message_api(channel_name, message, reply_parent_message_id, retry=False)
                if r.status == 200:
                    sent = (data.get("data") or [{}])[0]
                    if sent.get("is_sent", True):
                        self._last_chat_api_error = ""
                        return True
                    reason = sent.get("drop_reason") or {}
                    self._last_chat_api_error = reason.get("message") or str(reason)
                    logging.warning(f"⚠️ Chat Message API 被 Twitch 擋下 [{channel_name}]：{self._last_chat_api_error}")
                    return False
                error_text = ""
                if data:
                    error_text = data.get("message") or data.get("error") or str(data)
                self._last_chat_api_error = f"HTTP {r.status}" + (f"：{error_text}" if error_text else "")
                if channel_name not in self._chat_api_warned_channels:
                    self._chat_api_warned_channels.add(channel_name)
                    logging.warning(f"⚠️ Chat Message API 無法用於 {channel_name} ({self._last_chat_api_error})，會退回原本 IRC 發送。")
        except Exception as e:
            self._last_chat_api_error = str(e)
            if channel_name not in self._chat_api_warned_channels:
                self._chat_api_warned_channels.add(channel_name)
                logging.warning(f"⚠️ Chat Message API 發送失敗 [{channel_name}]，會退回原本 IRC 發送：{e}")
        return False

    async def send_chat_message(self, channel_name: str, message: str, reply_parent_message_id: str = None):
        channel_name = (channel_name or "").lower()
        message = str(message or "")[:500]
        if not channel_name or not message:
            return False

        if await self._send_chat_message_api(channel_name, message, reply_parent_message_id):
            return True

        ch = self.get_channel(channel_name)
        if ch:
            try:
                await ch.send(message)
                return True
            except Exception as e:
                logging.error(f"❌ IRC 降級發送失敗 [{channel_name}]: {e}")
        return False

    def _patch_context_chat_api(self, ctx):
        if getattr(getattr(commands, "Context", None), "_chat_api_class_patched", False):
            return
        if getattr(ctx, "_chat_api_patched", False):
            return
        try:
            orig_send = ctx.send
            orig_reply = ctx.reply
            ctx._chat_api_patched = True
        except Exception as e:
            logging.debug(f"Chat API context patch skipped: {e}")
            return

        async def api_send(content=None, *args, **kwargs):
            msg = content if content is not None else kwargs.get("content", "")
            ch_name = ctx.channel.name.lower() if ctx.channel and ctx.channel.name else ""
            if await self.send_chat_message(ch_name, msg):
                return None
            return await orig_send(content, *args, **kwargs)

        async def api_reply(content=None, *args, **kwargs):
            msg = content if content is not None else kwargs.get("content", "")
            ch_name = ctx.channel.name.lower() if ctx.channel and ctx.channel.name else ""
            parent_id = self._extract_message_id(getattr(ctx, "message", None))
            if await self.send_chat_message(ch_name, msg, parent_id):
                return None
            return await orig_reply(content, *args, **kwargs)

        try:
            ctx.send = api_send
            ctx.reply = api_reply
        except Exception as e:
            logging.debug(f"Chat API context patch failed: {e}")

    def _install_context_chat_api_patch(self):
        ctx_cls = getattr(commands, "Context", None)
        if not ctx_cls or getattr(ctx_cls, "_chat_api_class_patched", False):
            return

        orig_send = getattr(ctx_cls, "send", None)
        orig_reply = getattr(ctx_cls, "reply", None)
        if not orig_send or not orig_reply:
            return

        bot_ref = self

        async def api_send(ctx, content=None, *args, **kwargs):
            msg = content if content is not None else kwargs.get("content", "")
            ch_name = ctx.channel.name.lower() if ctx.channel and ctx.channel.name else ""
            if await bot_ref.send_chat_message(ch_name, msg):
                return None
            return await orig_send(ctx, content, *args, **kwargs)

        async def api_reply(ctx, content=None, *args, **kwargs):
            msg = content if content is not None else kwargs.get("content", "")
            ch_name = ctx.channel.name.lower() if ctx.channel and ctx.channel.name else ""
            parent_id = bot_ref._extract_message_id(getattr(ctx, "message", None))
            if await bot_ref.send_chat_message(ch_name, msg, parent_id):
                return None
            return await orig_reply(ctx, content, *args, **kwargs)

        ctx_cls.send = api_send
        ctx_cls.reply = api_reply
        ctx_cls._chat_api_class_patched = True

    # ==============================================================================
    # [5] 系統與錯誤防護區
    # ==============================================================================
    async def refresh_user_token(self):
        async with self.user_token_lock:
            if not self.user_refresh_token: return False
            try:
                async with self.session.post("https://id.twitch.tv/oauth2/token", params={"grant_type": "refresh_token", "refresh_token": self.user_refresh_token, "client_id": self.client_id, "client_secret": CLIENT_SECRET}) as r:
                    if r.status != 200: return False
                    d = await r.json(); self.user_access_token, self.user_refresh_token = d["access_token"], d.get("refresh_token", self.user_refresh_token)
                    await self.db.executemany("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", [("USER_ACCESS_TOKEN", self.user_access_token), ("USER_REFRESH_TOKEN", self.user_refresh_token)])
                    return True
            except: return False

    async def refresh_token(self):
        async with self.token_lock:
            try:
                async with self.session.post(f"https://id.twitch.tv/oauth2/token?client_id={self.client_id}&client_secret={CLIENT_SECRET}&grant_type=client_credentials") as r:
                    if "access_token" in (d := await r.json()): self.access_token = d["access_token"]
            except: pass

    async def validate_token_scopes(self):
        if self.user_access_token:
            try:
                async with self.session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {self.user_access_token}"}) as r:
                    if r.status == 200: self.token_owner_id = (await r.json()).get("user_id")
            except: pass

    async def get_public_ip(self):
        try:
            async with self.session.get("https://api.ipify.org?format=json", timeout=10) as r: return (await r.json()).get("ip") if r.status == 200 else None
        except: return None

    async def event_command_error(self, ctx, error):
        self._patch_context_chat_api(ctx)
        if isinstance(error, CommandOnCooldown):
            await ctx.reply(f"⏳ 指令冷卻中，還需等待 {error.retry_after:.0f} 秒")
        elif not isinstance(error, CommandNotFound):
            logging.error(f"Cmd Error: {error}")

    async def event_notice(self, *args):
        if ch := (args[0].channel.name.lower() if hasattr(args[0], 'channel') else args[0].name.lower() if hasattr(args[0], 'name') else None):
            self.last_message_time[ch] = time.time(); self.zombie_check_pending.pop(ch, None)

    async def _record_message_stats(self, message, c_name: str):
        try:
            author_id = str(message.author.id)
            self.chat_name_cache[message.author.display_name] = (author_id, message.author.name.lower(), message.author.display_name)

            await self.db.execute(
                "INSERT OR IGNORE INTO user_aliases (user_id, display_name, last_seen) VALUES (?, ?, ?)",
                (author_id, message.author.display_name, datetime.datetime.now(LOCAL_TZ).isoformat()),
            )

            if self.live_status.get(c_name, False):
                row = await self.db.fetchone("SELECT is_online FROM user_stats WHERE user_id=? AND channel=?", (author_id, c_name))
                if row and row[0] == 1:
                    await self.db.execute(
                        "UPDATE user_stats SET message_count = message_count + 1 WHERE user_id=? AND channel=?",
                        (author_id, c_name),
                    )
                else:
                    await self.db.execute(
                        "INSERT INTO user_stats (user_id, channel, is_online, last_entry_ts, watch_minutes, message_count) "
                        "VALUES (?, ?, 1, ?, 0, 1) "
                        "ON CONFLICT(user_id, channel) DO UPDATE SET "
                        "is_online = 1, last_entry_ts = excluded.last_entry_ts, message_count = message_count + 1",
                        (author_id, c_name, int(time.time())),
                    )

            if message.tags and 'vip' in message.tags.get('badges', {}):
                self.vip_batch.add((author_id, message.author.name.lower(), c_name, datetime.datetime.now(LOCAL_TZ).isoformat()))
        except Exception as e:
            logging.error(f"Message intercept error: {e}")

    async def _process_custom_commands(self, message, c_name: str) -> bool:
        if not message.content or not message.content.startswith('!'):
            return False

        cmd_name = message.content.split()[0][1:].lower()

        row = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"CMD_{c_name}_{cmd_name}",))
        if row:
            cd_key = f"CD_CMD_{c_name}_{cmd_name}"
            now = time.time()
            if now - getattr(self, cd_key, 0) > 5:
                setattr(self, cd_key, now)
                await self.send_chat_message(c_name, row[0], self._extract_message_id(message))
            return True

        return False

    async def event_message(self, message):
        if getattr(self, "_restarting", False): return
        if message.echo or not message.author: return

        c_name = message.channel.name.lower() if message.channel and message.channel.name else ""
        if not c_name: return

        self.last_message_time[c_name] = time.time()

        if c_name in SILENT_CHANNELS: return
        if message.author.name.lower() in IGNORED_BOTS: return

        if "嚴厲斥責" in message.content:
            now = time.time()
            cd_dict = getattr(self, "last_disclaimer_time", {})
            if now - cd_dict.get(c_name, 0) > 10:
                cd_dict[c_name] = now
                self.last_disclaimer_time = cd_dict
                msg_text = " imGlitch 本台嚴厲斥責任何形式之惡意言論，聊天室言論及抖內發言皆不代表本台主之立場。This channel of Guanweiboy strongly condemns any form of malicious and inappropriate speech. Statements made in the chat and through donations DO NOT represent the views of the channel owner. ItsBoshyTime ItsBoshyTime "
                # 🟢 使用紫色官方公告發送免責聲明
                await self._send_api_announce(c_name, msg_text, color="purple")

        if message.content and message.content.startswith('!'):
            parts = message.content.split(' ', 1)
            parts[0] = parts[0].lower()
            message.content = ' '.join(parts)

        if c_name in getattr(self, "_no_mod_channels", set()):
            self.active_chatters.setdefault(c_name, {})[str(message.author.id)] = time.time()

        await self._record_message_stats(message, c_name)

        if await self._process_custom_commands(message, c_name):
            return

        await self.handle_commands(message)

    async def verify_connection_on_startup(self, channel_name):
        # 1. 開台後給予 20 秒的靜默觀察時間
        await asyncio.sleep(20)

        ch = self.get_channel(channel_name)
        if not ch or not self._connection.is_alive:
            logging.warning(f"⚠️ {channel_name} 頻道物件遺失，執行隱形重連...")
            await self._rejoin_single_channel(channel_name)
            return

        # 2. 判斷觀察期內是否有任何動靜
        now = time.time()
        last_msg = self.last_message_time.get(channel_name, 0)

        if now - last_msg >= 20:
            # 使用 debug 層級，終端機不會被洗版
            logging.debug(f"🔍 {channel_name} 開台後 20 秒無動靜，執行背景隱形重連。")
            await self._rejoin_single_channel(channel_name)
        else:
            logging.debug(f"✅ {channel_name} 聊天室有動靜，連線確認正常！")

    def _is_ws_unhealthy(self):
        conn = getattr(self, "_connection", None)
        if not conn:
            return True
        if not getattr(conn, "is_alive", False):
            return True

        ws = getattr(conn, "_websocket", None)
        if ws:
            if getattr(ws, "closed", False):
                return True
            close_code = getattr(ws, "close_code", None)
            if close_code:
                return True
            transport = getattr(ws, "_writer", None)
            transport = getattr(transport, "transport", None)
            if transport and getattr(transport, "is_closing", lambda: False)():
                return True
        return False

    async def _rejoin_single_channel(self, channel_name):
        """專門處理單一頻道的無痛重新連線，不影響其他頻道，聊天室完全隱形"""
        if self._is_ws_unhealthy():
            logging.warning(f"⚠️ {channel_name} 無法隱形重連：聊天室 WebSocket 已不健康，改用全域重啟。")
            await self.hard_restart("System_WebSocket_Unhealthy")
            return

        try:
            await self.part_channels([channel_name])
            await asyncio.sleep(1)  # 緩衝 1 秒
            await self.join_channels([channel_name])

            # 強制更新時間戳，避免無限迴圈
            self.last_message_time[channel_name] = time.time()
            # 🟢 降級為 debug，這樣 LOG 就不會一直跳出來洗版
            logging.debug(f"🔄 {channel_name} 預防性隱形重連完成！")
        except Exception as e:
            if "closing transport" in str(e).lower():
                logging.error(f"💥 {channel_name} 隱形重連遇到 closing transport，啟動全域重啟。")
                await self.hard_restart("System_Closing_Transport")
                return
            logging.error(f"❌ {channel_name} 隱形重連失敗: {e}")

    async def safe_channel_send(self, channel_name: str, message: str):
        try:
            if not await self.send_chat_message(channel_name, message):
                logging.debug(f"⚠️ 無法發送公告/訊息至 {channel_name}：尚未與該頻道建立連線。")
        except Exception as e:
            logging.error(f"❌ 向 {channel_name} 發送訊息時發生異常: {e}")

    # ==============================================================================
    # [6] 背景排程任務區
    # ==============================================================================
    async def _process_channel_watch_time(self, cl: str, now_ts: int):
        if cl in SILENT_CHANNELS: return

        if cl in getattr(self, "_no_mod_channels", set()):
            idle_limit = 900
            if cl in getattr(self, "active_chatters", {}):
                for uid, last_spoke in list(self.active_chatters[cl].items()):
                    if now_ts - last_spoke > idle_limit:
                        await self.db.execute("UPDATE user_stats SET is_online = 0, last_leave_ts = ? WHERE channel=? AND user_id=?", (now_ts, cl, uid))
                        del self.active_chatters[cl][uid]
            return

        bid = await self._get_user_id_by_login(cl)
        if not bid or not getattr(self, "bot_user_id", None): return

        headers = {"Client-ID": self.client_id, "Authorization": f"Bearer {self.user_access_token}"}
        chatters, cursor, api_ok = set(), "", True

        while True:
            url = f"https://api.twitch.tv/helix/chat/chatters?broadcaster_id={bid}&moderator_id={self.bot_user_id}&first=1000"
            if cursor: url += f"&after={cursor}"
            async with self.session.get(url, headers=headers) as r:
                if int(r.headers.get('Ratelimit-Remaining', 800)) < 50:
                    logging.warning(f"⚠️ API 額度過低，放棄本次點名讓路給主指令")
                    api_ok = False; break
                if r.status == 401:
                    if not await self.refresh_user_token():
                        api_ok = False; break
                    headers["Authorization"] = f"Bearer {self.user_access_token}"
                    continue  # token 刷新成功，重試同一頁
                if r.status == 403:
                    logging.warning(f"⚠️ 缺乏 {cl} 的 Mod 權限，已將該台轉為被動超時稽查模式。")
                    if not hasattr(self, "_no_mod_channels"): self._no_mod_channels = set()
                    self._no_mod_channels.add(cl); api_ok = False; break
                if r.status != 200: break

                data = await r.json()
                ignored_bots = {
                    "nightbot", "streamelements", "fossabot", "soundalerts",
                    "kofkof", "alienguytim", "commanderroot", "wizebot", "chiwabots",
                    getattr(self, "nick", "").lower(), cl
                }
                chatters.update(c["user_id"] for c in data.get("data", []) if c["user_login"].lower() not in ignored_bots)
                cursor = data.get("pagination", {}).get("cursor")
                if not cursor: break
                await asyncio.sleep(0.1)

        if not api_ok or not chatters: return

        prev_online = {r[0] for r in await self.db.fetchall("SELECT user_id FROM user_stats WHERE channel=? AND is_online=1", (cl,))}

        if joined := chatters - prev_online:
            join_data = [(u, cl, now_ts) for u in joined]
            await self.db.executemany("INSERT INTO user_stats (user_id, channel, is_online, last_entry_ts, watch_minutes, message_count) VALUES (?, ?, 1, ?, 0.5, 0) ON CONFLICT(user_id, channel) DO UPDATE SET is_online = 1, last_entry_ts = excluded.last_entry_ts, watch_minutes = watch_minutes + 0.5", join_data)

        if here := chatters & prev_online:
            for i in range(0, len(here), 500):
                chunk = list(here)[i:i+500]
                placeholders = ",".join("?" for _ in chunk)
                await self.db.execute(f"UPDATE user_stats SET watch_minutes = watch_minutes + 0.5 WHERE channel=? AND user_id IN ({placeholders})", [cl] + chunk)

        if left := prev_online - chatters:
            for i in range(0, len(left), 500):
                chunk = list(left)[i:i+500]
                placeholders = ",".join("?" for _ in chunk)
                await self.db.execute(f"UPDATE user_stats SET is_online = 0, last_leave_ts = ? WHERE channel=? AND user_id IN ({placeholders})", [now_ts, cl] + chunk)

    async def _refill_regular_queue(self, ch):
        pool = list(STATIC_ANNOUNCEMENTS)
        try: pool.extend([r[0] for r in await self.db.fetchall("SELECT content FROM announcements WHERE is_session_only = 0 AND channel = ?", (ch,))])
        except Exception as e: logging.error(f"讀取常駐公告失敗: {e}")
        if pool:
            random.shuffle(pool)
            self.regular_queue[ch] = pool

    async def announce_regular_task(self):
        await asyncio.sleep(INTERVAL_REGULAR)
        strikes = 0
        while True:
            try:
                if not self._connection.is_alive: raise Exception("WebSocket Dead")
                for ch in self.connected_channels:
                    cl = ch.name.lower()
                    if cl in ANNOUNCE_CHANNELS and cl not in self.announce_disabled_channels and self.live_status.get(cl, False):
                        try:
                            if cl not in self.regular_queue or not self.regular_queue[cl]:
                                await self._refill_regular_queue(cl)

                            if self.regular_queue.get(cl):
                                msg = self.regular_queue[cl].pop(0)
                                await self.safe_channel_send(cl, msg)
                        except Exception as e: logging.warning(f"⚠️ [{cl}] 常駐公告發送失敗: {e}")
                strikes = 0
                await asyncio.sleep(INTERVAL_REGULAR)
            except Exception as e:
                strikes += 1
                if strikes >= 5:
                    logging.error(f"💥 偵測到 常駐公告 連續 50 秒無回應，啟動自動救援！")
                    await self.hard_restart("Auto_Fix_Regular_Fail")
                    return
                await asyncio.sleep(10)

    async def watch_time_tracker_task(self):
        await asyncio.sleep(15)
        while True:
            try:
                await asyncio.sleep(30)
                now_ts = int(time.time())
                for ch in self.connected_channels:
                    cl = ch.name.lower()
                    if not self.live_status.get(cl, False): continue
                    await self._process_channel_watch_time(cl, now_ts)
            except Exception as e:
                logging.error(f"watch_time_tracker loop error: {e}")
                await asyncio.sleep(5)

    async def monitor_ip_change(self):
        while True:
            try:
                await asyncio.sleep(60)
                if (new_ip := await self.get_public_ip()) and self.current_ip and new_ip != self.current_ip:
                    logging.warning(f"⚠️ IP 異動：{self.mask_ip(self.current_ip)} -> {self.mask_ip(new_ip)}")
                    self.current_ip = new_ip; await self.hard_restart("System_IP_Change")
            except: await asyncio.sleep(5)

    async def cleanup_cache_task(self):
        while True:
            try:
                await asyncio.sleep(43200); now = time.time()
                for k in [k for k, v in self.display_name_cache_ttl.items() if now - v[0] > 86400]: del self.display_name_cache_ttl[k]
                if len(self._user_cache) > 10000: self._user_cache.clear()
                stale_cd = [k for k, v in self.cooldowns.items() if now > v + 86400]
                for k in stale_cd: del self.cooldowns[k]
                self.chat_name_cache.clear()
            except: await asyncio.sleep(5)

    async def flush_vip_data_task(self):
        while True:
            try:
                await asyncio.sleep(30)
                if self.vip_batch:
                    await self.db.executemany("INSERT INTO known_vips (user_id, user_login, channel, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, channel) DO UPDATE SET user_login=?, last_seen=?", [(d[0], d[1], d[2], d[3], d[1], d[3]) for d in list(self.vip_batch)])
                    self.vip_batch.clear()
            except: await asyncio.sleep(5)

    async def periodic_mod_refresh(self):
        while True:
            try:
                await asyncio.sleep(self._mod_refresh_interval)
                for ch in self.connected_channels: self.mod_cache[ch.name] = [m.lower() for m in await self.fetch_channel_moderators(ch.name)]
            except: await asyncio.sleep(5)

    async def health_watchdog_task(self):
        await asyncio.sleep(60)
        while True:
            try:
                await asyncio.sleep(60)
                now = time.time()
                if self._is_ws_unhealthy():
                    if self._ws_unhealthy_since is None:
                        self._ws_unhealthy_since = now
                    self._ws_dead_strikes += 1
                    logging.warning(f"⚠️ 聊天室 WebSocket 無回應 ({self._ws_dead_strikes}/3)")
                    if self._ws_dead_strikes >= 3 or now - self._ws_unhealthy_since >= 180:
                        await self.hard_restart("System_WebSocket_Dead")
                        return
                else:
                    self._ws_dead_strikes = 0
                    self._ws_unhealthy_since = None

                if self._api_fail_since and now - self._api_fail_since >= API_FAIL_RESTART_SECONDS:
                    logging.error("💥 Twitch API 長時間無法恢復，啟動自動重啟。")
                    await self.hard_restart("System_Twitch_API_Stall")
                    return

                any_live = any(self.live_status.get(c.strip().lower(), False) for c in INITIAL_CHANNELS)
                if not any_live and now - self._last_offline_keepalive >= OFFLINE_KEEPALIVE_INTERVAL:
                    self._last_offline_keepalive = now
                    logging.debug("🔄 離線保活：重新確認所有初始聊天室連線。")
                    for cl in INITIAL_CHANNELS:
                        cl = cl.strip().lower()
                        if not cl:
                            continue
                        if self._is_ws_unhealthy():
                            logging.warning("⚠️ 離線保活偵測到 WebSocket 不健康，改用全域重啟。")
                            await self.hard_restart("System_Offline_Keepalive_WS_Dead")
                            return
                        if not self.get_channel(cl):
                            await self._rejoin_single_channel(cl)
                            await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"health_watchdog_task error: {e}")
                await asyncio.sleep(5)

    async def track_streams_task(self):
        while True:
            try:
                channels_to_check = {c.strip().lower() for c in INITIAL_CHANNELS + [ch.name for ch in self.connected_channels]}
                for cl in channels_to_check:
                    await self._process_single_stream_status(cl)
                await asyncio.sleep(30)
            except Exception as e:
                logging.error(f"track_streams_task error: {e}")
                await asyncio.sleep(5)

    async def _process_single_stream_status(self, cl: str):
        sd = await self.fetch_stream_data(cl)
        if sd is None:
            return
        is_live = bool(sd)
        sid = sd[0]['id'] if is_live else None

        if is_live:
            started_dt = datetime.datetime.fromisoformat(sd[0]['started_at'].replace('Z', '+00:00')).astimezone(LOCAL_TZ)
            actual_start_ts, today = started_dt.timestamp(), started_dt.strftime("%Y-%m-%d")
        else:
            today = datetime.datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

        was_live = self.live_status.get(cl, False)
        self.live_status[cl] = is_live

        if is_live:
            if not was_live:
                self.last_message_time[cl], self.stream_start_times[cl] = time.time(), actual_start_ts
                logging.info(f"🔴 {cl} 開台偵測！ (ID: {sid})")

                if cl not in SILENT_CHANNELS:
                    self.loop.create_task(self.verify_connection_on_startup(cl))
                    db_date = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"LAST_STREAM_DATE_{cl}",))
                    if not db_date or db_date[0] != today:
                        await self.db.execute('INSERT INTO channel_stats (channel, stream_count) VALUES (?, 1) ON CONFLICT(channel) DO UPDATE SET stream_count = stream_count + 1', (cl,))
                        if db_date and db_date[0]:
                            await self.db.execute('INSERT OR REPLACE INTO bot_state VALUES (?, ?)', (f"PREV_STREAM_DATE_{cl}", db_date[0]))
                        await self.db.execute('INSERT OR REPLACE INTO bot_state VALUES (?, ?)', (f"LAST_STREAM_DATE_{cl}", today))

                await self._refill_regular_queue(cl)

            elif sid != self.last_stream_ids.get(cl):
                self.stream_start_times[cl] = actual_start_ts
                logging.info(f"🔄 {cl} 偵測到直播重啟！")

                if cl not in SILENT_CHANNELS:
                    db_date = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"LAST_STREAM_DATE_{cl}",))
                    if not db_date or db_date[0] != today:
                        await self.db.execute('UPDATE channel_stats SET stream_count = stream_count + 1 WHERE channel=?', (cl,))
                        if db_date and db_date[0]:
                            await self.db.execute('INSERT OR REPLACE INTO bot_state VALUES (?, ?)', (f"PREV_STREAM_DATE_{cl}", db_date[0]))
                        await self.db.execute('INSERT OR REPLACE INTO bot_state VALUES (?, ?)', (f"LAST_STREAM_DATE_{cl}", today))

        elif not is_live and was_live:
            self.stream_start_times.pop(cl, None)
            self._silence_strikes[cl] = 0
            self.regular_queue.pop(cl, None)
            logging.info(f"📴 {cl} 關台 - 重置觀眾")

            if cl not in SILENT_CHANNELS:
                await self.db.execute("UPDATE user_stats SET is_online = 0, last_leave_ts = ? WHERE channel = ? AND is_online = 1", (int(time.time()), cl))
                if cl in self.active_chatters:
                    self.active_chatters[cl].clear()

        self.last_stream_ids[cl] = sid

    async def monitor_chat_silence(self):
        """定時巡邏員：全面改用無痛單頻重連，捨棄危險的全機重啟"""
        while True:
            try:
                await asyncio.sleep(30)
                now = time.time()
                for cl in [c.name.lower() for c in self.connected_channels]:
                    if cl in SILENT_CHANNELS: continue

                    if not self.live_status.get(cl, False):
                        self._silence_strikes[cl] = 0; continue
                    if cl not in self.last_message_time:
                        self.last_message_time[cl] = now; continue

                    stream_duration = now - self.stream_start_times.get(cl, now)

                    # 判斷是否靜默超時
                    timeout_limit = TIMEOUT_WARMUP if stream_duration < WARMUP_DURATION else TIMEOUT_STABLE
                    if (now - self.last_message_time[cl]) > timeout_limit:
                        # 🟢 直接使用隱形重連，不再發送 /timeout，也不會觸發 hard_restart 炸毀全部頻道！
                        logging.debug(f"🔍 {cl} 聊天室長時間無動靜，執行背景隱形重連維持連線...")
                        await self._rejoin_single_channel(cl)
                        self._silence_strikes[cl] = 0
                    else:
                        self._silence_strikes[cl] = 0
            except Exception as e:
                logging.error(f"monitor_chat_silence error: {e}")
                await asyncio.sleep(5)

    async def daily_reset_task(self):
        while True:
            try:
                now = datetime.datetime.now(LOCAL_TZ); target = datetime.datetime.combine(now.date(), datetime.time(0, 0, tzinfo=LOCAL_TZ)) + datetime.timedelta(days=1)
                await asyncio.sleep((target - now).total_seconds()); logging.info("🌞 開始重置與備份"); await self.backup_database(); await asyncio.sleep(RESET_DELAY_SECONDS)
            except: await asyncio.sleep(5)

    async def monthly_reset_task(self):
        while True:
            try:
                now = datetime.datetime.now(LOCAL_TZ); month_str = now.strftime("%Y-%m")
                r = await self.db.fetchone("SELECT value FROM bot_state WHERE key='LAST_MONTHLY_RESET'")
                last_reset = r[0] if r else None
                if not last_reset:
                    await self.db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", ('LAST_MONTHLY_RESET', month_str))
                    logging.info(f"📅 初始化月重置紀錄：{month_str}，不執行歸零。")
                    await asyncio.sleep(5)
                    continue
                if last_reset != month_str:
                    logging.info(f"🔄 偵測到跨月未重置 ({last_reset} -> {month_str})，立即執行跨月重置作業！")
                    await self.reset_monthly_checkins(); await asyncio.sleep(5); continue

                next_month = now.replace(day=1) + relativedelta(months=1)
                target = datetime.datetime.combine(next_month.date(), datetime.time(0, 0, tzinfo=LOCAL_TZ))
                delta = target - now
                if delta.total_seconds() <= 0:
                    await self.reset_monthly_checkins(); await asyncio.sleep(60)
                else:
                    h, rem = divmod(delta.seconds, 3600); m, s = divmod(rem, 60)
                    msg = f"\r\033[K📅 月重置倒數：{delta.days}天 {h}時 {m}分 {s}秒 ｜ 💓 系統存活 ({len([c for c, l in self.live_status.items() if l])})"
                    for hdr in logging.getLogger().handlers:
                        if isinstance(hdr, CleanConsoleHandler): hdr.countdown_msg = msg; break
                    sys.stdout.write(msg); sys.stdout.flush()
                    await asyncio.sleep(1)
            except Exception as e: logging.error(f"Monthly Reset Error: {e}"); await asyncio.sleep(5)

    async def reset_monthly_checkins(self):
        curr_m, prev_m = datetime.datetime.now(LOCAL_TZ).strftime("%Y-%m"), (datetime.datetime.now(LOCAL_TZ).replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m"); await self.backup_database()
        for ch in [r[0] for r in await self.db.fetchall("SELECT DISTINCT channel FROM checkins")]:
            rows = await self.db.fetchall("SELECT user, monthly_count FROM checkins WHERE channel=? AND monthly_count > 0 ORDER BY monthly_count DESC LIMIT 10", (ch,)); names = await self.fetch_display_names_from_api([r[0] for r in rows])
            for i, (u, c) in enumerate(rows, 1): await self.db.execute("INSERT OR REPLACE INTO monthly_top5 VALUES (?, ?, ?, ?, ?, ?)", (ch, prev_m, i, u, names.get(u, u), c))
        await asyncio.gather(self.db.execute("DELETE FROM monthly_top5 WHERE month < ?", ((datetime.datetime.now(LOCAL_TZ) - relativedelta(months=TOP5_RETAIN_MONTHS)).strftime("%Y-%m"),)), self.db.execute("UPDATE checkins SET monthly_count = 0"), self.db.execute("UPDATE channel_stats SET stream_count = 0"), self.db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", ('LAST_MONTHLY_RESET', curr_m)))
        logging.info("✅ 月重置完成 (已備份、存榜單、歸零)")

    async def backup_database(self):
        now = datetime.datetime.now(LOCAL_TZ)
        ts = now.strftime("%Y%m%d_%H%M%S")
        fname = f"data/backups/checkin_backup_{ts}.db"
        try:
            await self.db.execute("PRAGMA wal_checkpoint(FULL);")
            os.makedirs("data/backups", exist_ok=True)
            await self.loop.run_in_executor(None, shutil.copy, "checkin.db", fname)
            logging.info(f"📦 備份成功: {fname}")
        except Exception as e: return logging.error(f"❌ 備份失敗: {e}")
        for f in [f for f in os.listdir("data/backups") if f.startswith("checkin_backup_") and f.endswith(".db")]:
            try:
                fd = datetime.datetime.strptime(f[15:23], "%Y%m%d").date()
                days_old = (now.date() - fd).days
                months_old = (now.year - fd.year) * 12 + (now.month - fd.month)
                is_month_boundary = (fd.day == 1 or fd.day == calendar.monthrange(fd.year, fd.month)[1])
                # 月首/月末備份保留 6 個月；其餘按 BACKUP_RETAIN_DAYS
                should_delete = (is_month_boundary and months_old > 6) or (not is_month_boundary and days_old >= BACKUP_RETAIN_DAYS)
                if should_delete:
                    os.remove(os.path.join("data/backups", f)); logging.info(f"🗑️ 已刪除過期備份: {f}")
            except: pass

    async def proposal_timeout_task(self, ctx, t_id, ts, ch):
        await asyncio.sleep(30)
        p_key = f"{t_id}_{ch}"
        if p_key in self.pending_proposals and self.pending_proposals[p_key]["ts"] == ts:
            del self.pending_proposals[p_key]
            try:
                await ctx.send(f"💔 求婚時間到... {ctx.author.display_name} 的求婚已失效。")
            except Exception:
                pass

    # ==============================================================================
    # [7] 聊天室指令區
    # ==============================================================================
    @commands.command(name='cu', aliases=['數據', '肝度'])
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def cmd_check_user_stats(self, ctx, target: str = None):
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.reply(f"⚠️ 找不到使用者 {target.strip().replace('@', '') if target else ctx.author.name}")

        ch = ctx.channel.name.lower()
        r = await self.db.fetchone("SELECT is_online, last_entry_ts, last_leave_ts, watch_minutes, message_count FROM user_stats WHERE user_id=? AND channel=?", (uid, ch))
        if not r: return await ctx.reply(f"📭 {dname} 目前沒有任何數據紀錄。")

        is_on, in_ts, out_ts, w_mins, m_cnt = r
        watch_str = self.format_watch_time(w_mins)

        hours = w_mins / 60
        if hours < 10: title = "小幼柴"
        elif hours < 50: title = "飛機柴"
        elif hours < 200: title = "胖胖柴"
        elif hours < 500: title = "拒否柴"
        elif hours < 1000: title = "柴犬王"
        elif hours < 2000: title = "神仙柴"
        else: title = "骨灰柴"

        my_exp = int(w_mins * 2 + m_cnt * 5)
        level = int((my_exp / 50) ** 0.5) + 1

        next_level_exp = (level ** 2) * 50
        exp_gap = next_level_exp - my_exp

        msg_needed = (exp_gap + 4) // 5
        mins_needed = (exp_gap + 1) // 2

        upgrade_hints = [f"{msg_needed} 則訊息", f"{self.format_watch_time(mins_needed)} 觀看"]
        upgrade_hint = random.choice(upgrade_hints)

        total_users_count = (await self.db.fetchone("SELECT COUNT(*) FROM user_stats WHERE channel=?", (ch,)))[0]
        higher_exp_count = (await self.db.fetchone("SELECT COUNT(*) FROM user_stats WHERE channel=? AND (watch_minutes * 2 + message_count * 5) > ?", (ch, my_exp)))[0]
        total_rank = higher_exp_count + 1

        entry_time = self.format_hhmm(in_ts)
        leave_time = self.format_hhmm(out_ts) if out_ts else "--:--"
        if is_on:
            status_msg = f"🟢 | 🚪進入: {entry_time}"
        elif out_ts and int(time.time()) - out_ts < 86400:
            status_msg = f"🔴/首次{entry_time}/離開{leave_time} | 🕐最後離開: {self.format_time_ago(out_ts)}"
        else:
            status_msg = f"🔴 | 🕐最後離開: {self.format_time_ago(out_ts)}"

        # 🟢 判斷是不是查自己：查別人加【名字】，查自己不加
        is_self = (uid == str(ctx.author.id))
        name_prefix = "" if is_self else f"【{dname}】 "

        final_msg = f"{name_prefix}[{title}] Lv.{level} (排第 {total_rank} / 共 {total_users_count} 名) {status_msg} | 👀 {watch_str} / 💬 {m_cnt} (升級還需 {upgrade_hint})"
        await ctx.reply(final_msg)

    @commands.command(name='前世', aliases=['查水表', 'audit'])
    @commands.cooldown(1, 10, commands.Bucket.user)
    @safe_command
    async def cmd_audit_names(self, ctx, target: str = None):
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.reply(f"❌ 找不到使用者 {target.strip().replace('@', '') if target else ctx.author.name}")

        if not (rows := await self.db.fetchall("SELECT display_name, last_seen FROM user_aliases WHERE user_id=? ORDER BY last_seen DESC", (uid,))):
            return await ctx.reply(f"📭 {dname} 沒有改名紀錄。")

        msg = f"🔍 【{dname}】 的前世今生：\n" + " ➜ ".join([f"{r[0]} ({r[1][:10] if r[1] else '未知'})" for r in rows])
        await ctx.reply(msg[:440] + "...(略)" if len(msg) > 450 else msg)

    @commands.command(name='加公告')
    @require_general_admin
    @safe_command
    async def cmd_add_announce(self, ctx, *, content: str):
        ch = ctx.channel.name.lower()
        await self.db.execute("INSERT INTO announcements (channel, content, added_at, added_by, is_session_only) VALUES (?, ?, ?, ?, 0)", (ch, content, datetime.datetime.now(LOCAL_TZ).isoformat(), ctx.author.name))
        await ctx.reply(f"✅ 已新增永久公告：{content}")

    @commands.command(name="簽到開關")
    @require_general_admin
    @safe_command
    async def toggle_sign(self, ctx):
        v, t, m = (1, "discard", "開啟") if (ch := ctx.channel.name.lower()) in self.signin_disabled_channels else (0, "add", "關閉")
        getattr(self.signin_disabled_channels, t)(ch); await self.db.execute("INSERT INTO channel_settings (channel, signin_enabled) VALUES (?, ?) ON CONFLICT(channel) DO UPDATE SET signin_enabled=?", (ch, v, v)); await ctx.reply(f"{'✅' if v else '🚫'} 簽到已【{m}】！")

    @commands.command(name="定時開關", aliases=["公告開關"])
    @require_general_admin
    @safe_command
    async def toggle_announce(self, ctx):
        v, t, m = (1, "discard", "開啟") if (ch := ctx.channel.name.lower()) in self.announce_disabled_channels else (0, "add", "關閉")
        getattr(self.announce_disabled_channels, t)(ch); await self.db.execute("INSERT INTO channel_settings (channel, announce_enabled) VALUES (?, ?) ON CONFLICT(channel) DO UPDATE SET announce_enabled=?", (ch, v, v)); await ctx.reply(f"{'📢' if v else '🔕'} 定時公告已【{m}】！")

    @commands.command(name="簽到")
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def sign_in(self, ctx):
        uid, uname, dname, ch = str(ctx.author.id), ctx.author.name.lower(), ctx.author.display_name, ctx.channel.name.lower()
        if ch in self.signin_disabled_channels: return
        if not (sd := await self.fetch_stream_data(ch)): return await ctx.reply(f"{dname}，目前非直播狀態，無法簽到。")
        sid = sd[0]['id']; now = int(time.time())
        started_dt = datetime.datetime.fromisoformat(sd[0]['started_at'].replace('Z', '+00:00')).astimezone(LOCAL_TZ)
        stream_logical_date = started_dt.strftime("%Y-%m-%d")
        await self.db.execute("INSERT OR REPLACE INTO user_aliases VALUES (?, ?, ?)", (uid, dname, datetime.datetime.now(LOCAL_TZ).isoformat()))
        if r := await self.db.fetchone("SELECT last_stream_id, last_checkin FROM checkins WHERE user_id=? AND channel=?", (uid, ch)):
            if r[0] == sid: return await ctx.reply(f"{dname}，這場直播已簽到過囉！等下次開台再簽！ cmonBruh")
            if r[1] == stream_logical_date: return await ctx.reply(f"{dname}，今天已經簽到過了喔！")
        await self.db.execute(
            "INSERT INTO checkins "
            "(user_id, user, display_name, channel, count, last_checkin, last_checkin_ts, total_count, monthly_count, last_stream_id) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, 1, 1, ?) "
            "ON CONFLICT(user_id, channel) DO UPDATE SET "
            "count = count + 1, total_count = total_count + 1, monthly_count = monthly_count + 1, "
            "last_checkin = excluded.last_checkin, last_checkin_ts = excluded.last_checkin_ts, "
            "user = excluded.user, display_name = excluded.display_name, last_stream_id = excluded.last_stream_id",
            (uid, uname, dname, ch, stream_logical_date, now, sid),
        )
        if r := await self.db.fetchone("SELECT monthly_count, total_count FROM checkins WHERE user_id=? AND channel=?", (uid, ch)):
            await ctx.reply(f"{dname}簽到成功！本月：{r[0]} 次，總共：{r[1]} 次！ DinoDance")

    @commands.command(name="查詢")
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def query(self, ctx, target: str = None):
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.reply(f"⚠️ 找不到使用者 {target.strip().replace('@', '') if target else ctx.author.name}")

        is_self = (uid == str(ctx.author.id))
        if not is_self and not (ctx.author.is_vip or has_permission(ctx)):
            return await ctx.reply(f"🚫 {ctx.author.display_name} 只有 VIP 以上身份才能查詢其他人！")

        ch = ctx.channel.name.lower()
        row = await self.db.fetchone("SELECT user, display_name, last_checkin, total_count, monthly_count FROM checkins WHERE user_id=? AND channel=?", (uid, ch))
        sc = (await self.db.fetchone("SELECT stream_count FROM channel_stats WHERE channel=?", (ch,)) or [0])[0]

        def days_ago_label(d):
            n = (datetime.datetime.now(LOCAL_TZ).date() - d).days
            ago = "今天" if n <= 0 else "昨天" if n == 1 else f"{n} 天前"
            return f"{d.month}/{d.day}（{ago}）"

        is_live_now = self.live_status.get(ch, False) and ch in self.stream_start_times
        if is_live_now:
            # 直播中：LAST_STREAM_DATE 已被覆寫成今天，改讀「上一個有開台的日曆日」PREV_STREAM_DATE，
            # 這樣不論直播中或離線查詢，看到的「上次開台」都是同一個基準（開台日，不受跨夜下播影響）
            prev_row = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"PREV_STREAM_DATE_{ch}",))
            prev_date = None
            if prev_row and prev_row[0]:
                try:
                    prev_date = datetime.datetime.strptime(prev_row[0], "%Y-%m-%d").date()
                except ValueError:
                    pass
            if prev_date is None:
                # 過渡期備援：PREV_STREAM_DATE 要等下一次跨日開台才會寫入，舊資料 OFFLINE_TS 先頂著顯示
                legacy_row = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"OFFLINE_TS_{ch}",))
                if legacy_row and legacy_row[0]:
                    try:
                        prev_date = datetime.datetime.fromtimestamp(float(legacy_row[0]), LOCAL_TZ).date()
                    except (ValueError, OSError):
                        pass
            prev_label = f" ｜ 上次開台：{days_ago_label(prev_date)}" if prev_date else ""
            live_msg = f"(🟢 本月第 {sc} 次開播，今日於 {self.format_hhmm(self.stream_start_times[ch])} 開台{prev_label})"
        else:
            date_row = await self.db.fetchone("SELECT value FROM bot_state WHERE key=?", (f"LAST_STREAM_DATE_{ch}",))
            if date_row and date_row[0]:
                try:
                    last_date = datetime.datetime.strptime(date_row[0], "%Y-%m-%d").date()
                    live_msg = f"(💤 上次開台：{days_ago_label(last_date)} ｜ 本月累計開播 {sc} 次)"
                except ValueError:
                    live_msg = f"(🔴本月累計開播 {sc} 次)"
            else:
                live_msg = f"(🔴本月累計開播 {sc} 次)"

        if row:
            await ctx.reply(f"🔍 【{row[1] or dname}】的簽到紀錄｜本月：{row[4]}次｜總計：{row[3]}次｜最後簽到：{str(row[2]).split()[0] if row[2] else '未知'} {live_msg}")
        else:
            await ctx.reply(f"🔍 【{dname}】尚無紀錄，請輸入 !簽到 開始！ {live_msg}" if is_self else f"📭 【{dname}】目前沒有紀錄。")

    @commands.command(name='我的排名')
    @commands.cooldown(1, 10, commands.Bucket.user)
    @safe_command
    async def my_rank(self, ctx, target: str = None):
        if target and not has_permission(ctx): return
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.reply("❌ 找不到使用者")

        ch = ctx.channel.name.lower()
        r = await self.db.fetchone("SELECT count, monthly_count FROM checkins WHERE user_id=? AND channel=?", (uid, ch))
        if not r: return await ctx.send(f"{dname} 還沒簽到過！")

        u_count, u_month = r
        rank = (await self.db.fetchone("SELECT COUNT(*) FROM checkins WHERE channel=? AND count > ?", (ch, u_count)))[0] + 1
        await ctx.reply(f"{dname} 排名：第 {rank} 名，本月 {u_month} 次，累積 {u_count} 次")

    @commands.command(name='本月排名')
    @commands.cooldown(1, 10, commands.Bucket.channel)
    @safe_command
    async def top_monthly(self, ctx):
        if not (rows := await self.db.fetchall("SELECT user, monthly_count FROM checkins WHERE channel=? AND monthly_count > 0 ORDER BY monthly_count DESC LIMIT 10", (ctx.channel.name.lower(),))): return await ctx.send("目前還沒有紀錄！")
        names = await self.fetch_display_names_from_api([r[0] for r in rows])
        msg = "🏆 本月排名：" + "".join([f"｜{i+1}. {names.get(u, u)}（{c}次）" for i, (u, c) in enumerate(rows)])
        await ctx.send(msg[:495] + "..." if len(msg) > 500 else msg)

    @commands.command(name="月排名")
    @commands.cooldown(1, 10, commands.Bucket.channel)
    @safe_command
    async def last_month_top5(self, ctx, m: str = None):
        if m and not re.match(r"^\d{4}-\d{2}$", m): return await ctx.reply("❌ 格式錯誤 (YYYY-MM)")
        tm = m or (datetime.datetime.now(LOCAL_TZ).replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
        if rows := await self.db.fetchall("SELECT rank, display_name, count FROM monthly_top5 WHERE channel=? AND month=? ORDER BY rank ASC LIMIT 10", (ctx.channel.name.lower(), tm)):
            msg = f"🏆 {tm} 的前十名：" + "".join([f"｜{r}. {n}（{c}次）" for r, n, c in rows])
            await ctx.send(msg[:495] + "..." if len(msg) > 500 else msg)
        else: await ctx.send(f"📭 {tm} 沒有紀錄！")

    @commands.command(name='幫助')
    @safe_command
    async def help(self, ctx): await ctx.reply("📌 BOT指令列表：https://tinyurl.com/2d3zf8fy")

    @commands.command(name='備份')
    @require_general_admin
    @safe_command
    async def backup_command(self, ctx):
        await self.backup_database(); await ctx.reply(f"📦 備份完成。")

    @commands.command(name='重啟')
    @require_general_admin
    @safe_command
    async def restart_command(self, ctx):
        asyncio.create_task(self.hard_restart(ctx.channel.name.lower(), is_manual=True))

    @commands.command(name="測試")
    @require_general_admin
    @safe_command
    async def pingcheck(self, ctx):
        async with self.session.get(f"https://api.twitch.tv/helix/streams?user_login={ctx.channel.name}", headers={"Authorization": f"Bearer {self.access_token}", "Client-Id": self.client_id}) as r:
            if r.status == 200: await ctx.send("✅ Ping 成功！")
            elif r.status == 401: await self.refresh_token(); await ctx.send("🔑 Token 刷新！")
            else: await ctx.send(f"⚠️ API 異常 ({r.status})")

    @commands.command(name="狀態")
    @require_general_admin
    @safe_command
    async def status(self, ctx):
        ch = ctx.channel.name.lower()
        u, c = self.format_uptime_digital(self.start_time), (await self.db.fetchone("SELECT COUNT(DISTINCT user_id) FROM checkins WHERE channel=?", (ch,)) or [0])[0]
        s = f"⚠️ 靜默 ({st})" if self.live_status.get(ch, False) and (st := self._silence_strikes.get(ch, 0)) > 0 else ("🟢 監控中" if self.live_status.get(ch, False) else "🔴 未開台")
        await ctx.send(f"🤖運作時間：{u} ｜ 本台簽到數：{c} ｜ {s} (v{self.bot_version})")

    @commands.command(name="創建多久")
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def creation_date(self, ctx, target: str = None):
        if target and not (ctx.author.is_vip or has_permission(ctx)): return
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.send(f"⚠️ 找不到 {target.strip().replace('@', '') if target else ctx.author.name}")

        async with self.session.get(f"https://api.twitch.tv/helix/users?id={uid}", headers={"Authorization": f"Bearer {self.access_token}", "Client-Id": self.client_id}) as r:
            if (d := await r.json()).get("data"):
                dt = datetime.datetime.fromisoformat(d["data"][0]["created_at"].replace("Z", "+00:00"))
                await ctx.send(f"📅 {dname} 建立於 {dt.year}-{dt.month}-{dt.day} ({self.format_duration_zh(dt)})")
            else: await ctx.send(f"⚠️ API 錯誤")

    @commands.command(name="芯寶", aliases=["追隨時間", "followage"])
    @commands.cooldown(1, 10, commands.Bucket.user)
    @safe_command
    async def follow_duration(self, ctx):
        parts = ctx.message.content.split()
        target = parts[1] if len(parts) > 1 else None

        uid, t_login, t_name = await self.resolve_target(ctx, target)
        if not uid:
            raw_t = target.replace("@", "").strip().lower()
            t_login, t_name = raw_t, raw_t

        ch = ctx.channel.name.lower()
        ch_name = self.broadcaster_name_map.get(ch, (0,0,ch))[2]

        if t_login == ch:
            return await ctx.reply(f"😆 {t_name} 就是台主本人啦！(無法追隨自己)")

        url = f"https://api.ivr.fi/v2/twitch/subage/{t_login}/{ch}"

        try:
            async with self.session.get(url) as r:
                if r.status == 200:
                    data = await r.json()
                    followed_at = data.get("followedAt")

                    if not followed_at:
                        await ctx.reply(f"💔 {t_name} 還沒追隨 {ch_name} 喔！")
                    else:
                        dt = datetime.datetime.fromisoformat(followed_at.replace("Z", "+00:00"))
                        duration_str = self.format_duration_zh(dt)
                        await ctx.reply(f"💖 {t_name} 已追隨 {ch_name} {duration_str}！")
                elif r.status == 404:
                    await ctx.reply(f"❌ 找不到該使用者，可能帳號已不存在。")
                else:
                    await ctx.reply(f"⚠️ IVR API 暫時無回應 (狀態碼: {r.status})")
        except Exception as e:
            logging.error(f"IVR API 追隨查詢失敗: {e}")
            await ctx.reply(f"⚠️ 查詢失敗，請稍後再試。")

    @commands.command(name="B人", aliases=["b人","600"])
    @safe_command
    async def cmd_ban_user(self, ctx, *args):
        a_id, a_name, ch = str(ctx.author.id), ctx.author.name.lower(), ctx.channel.name.lower(); is_admin, is_vip = has_permission(ctx), ctx.author.is_vip
        if ch in getattr(self, "_no_mod_channels", set()): return
        l_max, cd = (86400, 0) if is_admin else ((3600, 3) if is_vip else (600, 10)); t_in, sec = a_name, 600
        if args:
            for arg in args:
                if arg == "隨機": sec = random.randint(60, 600)
                elif arg.isdigit() and len(arg) <= 6: sec = int(arg)
                else: t_in = arg.replace("@", "")
            if len(args) == 1 and args[0].isdigit() and await self.get_smart_user(args[0]): t_in, sec = args[0], 600
        t_id, t_name = u[0:3:2] if (u := await self.get_smart_user(t_in)) else (t_in, t_in) if t_in.isdigit() else (None, None)
        if not t_id: return await ctx.send(f"❌ 找不到: {t_in}")
        if t_id == await self._get_user_id_by_login(ch):
            await ctx.send(f"🛡️ 反彈！ {ctx.author.display_name} 擊暈 10 秒！"); return await self._timeout_via_api(ch, a_id, 10)
        cd_key = f"{a_name}_{ch}"
        if not is_admin and time.time() < self.cooldowns.get(cd_key, 0): return await ctx.send(f"⌛ 冷卻中")
        if not is_admin: self.cooldowns[cd_key] = time.time() + cd
        actual_sec = max(1, min(sec, l_max))
        ok, msg = await self._timeout_via_api(ch, t_id, actual_sec, "Bot Ban")
        if not ok and ("403" in msg or "401" in msg):
            if not hasattr(self, "_no_mod_channels"): self._no_mod_channels = set()
            self._no_mod_channels.add(ch); return
        h, r = divmod(actual_sec, 3600); m, s = divmod(r, 60)
        time_str = f"{h}小時{m}分{s}秒" if h > 0 else f"{m}分{s}秒" if m > 0 else f"{s}秒"

        if ok:
            logging.info(f"🔨 [執法紀錄] {t_name} 被禁言 {time_str}")
            await self._send_api_announce(ch, f"🔨 {t_name} 被禁言 {time_str}！", color="primary")
        else:
            await ctx.send(f"❌ 失敗：{msg}")

    @commands.command(name="解B", aliases=["unban", "解b"])
    @safe_command
    async def cmd_unban_user(self, ctx, target: str = None):
        if not has_permission(ctx): return
        ch = ctx.channel.name.lower()
        if ch in getattr(self, "_no_mod_channels", set()): return

        if not target:
            try:
                rows = await self.db.fetchall("SELECT user_id, user_login FROM known_vips WHERE channel=?", (ch,))
                if not rows: return await ctx.send("📭 資料庫中目前沒有本台的 VIP 紀錄。")

                logins = [r[1] for r in rows]
                names_dict = await self.fetch_display_names_from_api(logins)
                rescued_names = []

                for i, (uid, uname) in enumerate(rows):
                    ok, msg = await self._unban_via_api(ch, uid)
                    if ok:
                        rescued_names.append(names_dict.get(uname, uname))
                    elif "401" in msg or "403" in msg:
                        if not hasattr(self, "_no_mod_channels"): self._no_mod_channels = set()
                        self._no_mod_channels.add(ch)
                        return

                    if (i + 1) % 15 == 0: await asyncio.sleep(1.5)
                    else: await asyncio.sleep(0.1)

                if rescued_names:
                    await self._send_api_announce(ch, f"🚑 VIP 救援成功！已為 {', '.join(rescued_names)} 解除禁言。", color="green")
                else:
                    await ctx.send("✅ 掃描完畢，目前沒有任何 VIP 被禁言！")
            except Exception as e:
                logging.error(f"Unban Auto Error: {e}")
                await ctx.send("⚠️ 內部錯誤：掃描中斷")
            return

        t_id, _, t_dname = u if (u := await self.get_smart_user(target)) else (None, None, None)
        if not t_id: return await ctx.reply(f"❌ 找不到使用者 {target}")

        ok, msg = await self._unban_via_api(ch, t_id)
        if ok:
            logging.info(f"🚑 [執法紀錄] {t_dname} 被解除禁言")
            await self._send_api_announce(ch, f"🚑 {t_dname} 解除禁言成功！", color="green")
        elif "403" in msg or "401" in msg:
            if not hasattr(self, "_no_mod_channels"): self._no_mod_channels = set()
            self._no_mod_channels.add(ch)
            return
        elif "該觀眾目前並未被禁言" in msg:
            await ctx.send(f"⚠️ {t_dname} 目前沒有被禁言喔！")
        else:
            await ctx.send(f"❌ 解除失敗: {msg}")

    @commands.command(name='求婚', aliases=['marry'])
    @safe_command
    async def cmd_propose(self, ctx, target: str = None):
        if not target: return await ctx.reply("💍 例：!求婚 @小明")
        s_id, ch = str(ctx.author.id), ctx.channel.name.lower()

        t_id, t_login, t_dname = await self.resolve_target(ctx, target)
        if not t_id: return await ctx.reply("❌ 找不到對象！")

        if t_id == await self._get_user_id_by_login(ch) and ctx.author.name.lower() not in BOT_ADMINS: return await ctx.reply(self.broadcaster_propose_replies.get(ch, "🚫 台主不能娶！"))
        if t_login == ctx.author.name.lower(): return await ctx.reply("💔 不能跟自己結...")
        if await self.db.fetchone("SELECT 1 FROM marriages WHERE user1_id=? AND user2_id=? AND channel=?", (s_id, t_id, ch)): return await ctx.reply(f"🚫 你們已經是夫妻了！")
        if c := await self.db.fetchone("SELECT user2_name FROM marriages WHERE user1_id=? AND channel=?", (t_id, ch)): return await ctx.reply(f"🚫 【{t_dname}】 名花有主（伴侶：{c[0]}）！")

        p_key = f"{t_id}_{ch}"
        if p_key in self.pending_proposals: return await ctx.reply(f"💍 【{t_dname}】正考慮其他求婚！")
        ts = time.time(); self.pending_proposals[p_key] = {"pid": s_id, "pname": ctx.author.display_name, "ts": ts}
        await ctx.send(f"💍 {ctx.author.display_name} 向 {t_dname} 求婚！ 30 秒內輸入 !yes 答應！")
        self.loop.create_task(self.proposal_timeout_task(ctx, t_id, ts, ch))

    @commands.command(name='yes', aliases=['我願意', 'accept'])
    @safe_command
    async def cmd_accept_marriage(self, ctx):
        uid, uname, ch = str(ctx.author.id), ctx.author.display_name, ctx.channel.name.lower()
        p_key = f"{uid}_{ch}"
        if not (p := self.pending_proposals.get(p_key)): return await ctx.reply("⌛ 求婚已過期！")
        pid, pname, td = p["pid"], p["pname"], datetime.datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
        await self.db.executemany("INSERT OR REPLACE INTO marriages VALUES (?, ?, ?, ?, ?, ?)", [(uid, uname, pid, pname, ch, td), (pid, pname, uid, uname, ch, td)])
        self.pending_proposals.pop(p_key, None)

        c = (await self.db.fetchone("SELECT COUNT(*) FROM marriages WHERE user1_id=? AND channel=?", (pid, ch)) or [1])[0]
        title = HAREM_TITLES[c-1] if c <= len(HAREM_TITLES) else f"第 {c} 房姨太"
        await ctx.send(f"🏮 恭喜！{uname} 與 {pname} 締結良緣，冊封為【{title}】！")

    @commands.command(name='cp', aliases=['伴侶', '老公', '老婆', '后宮'])
    @safe_command
    async def cmd_check_partner(self, ctx, target: str = None):
        if target and not (ctx.author.is_vip or has_permission(ctx)): return
        uid, _, dname = await self.resolve_target(ctx, target)
        if not uid: return await ctx.reply("❌ 找不到該使用者！")

        rows = await self.db.fetchall("SELECT user2_name FROM marriages WHERE user1_id=? AND channel=? ORDER BY marriage_date ASC", (uid, ctx.channel.name.lower()))
        if rows:
            harem_list = [f"｜{HAREM_TITLES[i] if i < len(HAREM_TITLES) else f'第 {i+1} 房'}:{r[0]}" for i, r in enumerate(rows)]
            await ctx.reply(f"🌸 【{dname}】後宮：" + "".join(harem_list))
        else:
            await ctx.reply(f"🍃 【{dname}】目前單身。")

    @commands.command(name='divorce', aliases=['離婚'])
    @safe_command
    async def cmd_divorce(self, ctx, target: str = None):
        uid, ch = str(ctx.author.id), ctx.channel.name.lower()
        d_key = f"{uid}_{ch}"
        if not target:
            if not (rows := await self.db.fetchall("SELECT user2_id, user2_name FROM marriages WHERE user1_id=? AND channel=?", (uid, ch))): return await ctx.reply("❓ 還沒結啊？")
            if len(rows) > 1: return await ctx.reply(f"⚠️ 多位後宮，請指定：!離婚 @對象")
            self.pending_divorces[d_key] = {"t_id": rows[0][0], "t_name": rows[0][1], "ts": time.time()}
            return await ctx.reply(f"💔 請在 30 秒內輸入 !確認離婚。")

        t_id, _, t_name = await self.resolve_target(ctx, target)
        if not t_id or not await self.db.fetchone("SELECT 1 FROM marriages WHERE user1_id=? AND user2_id=? AND channel=?", (uid, t_id, ch)): return await ctx.reply("❓ 無婚姻關係。")

        self.pending_divorces[d_key] = {"t_id": t_id, "t_name": t_name, "ts": time.time()}
        await ctx.reply(f"💔 確定休了 {t_name}？ 30 秒內 !確認離婚")

    @commands.command(name='確認離婚')
    @safe_command
    async def cmd_confirm_divorce(self, ctx):
        uid, ch = str(ctx.author.id), ctx.channel.name.lower()
        d_key = f"{uid}_{ch}"
        if not (p := self.pending_divorces.get(d_key)) or time.time() - p["ts"] > 30:
            self.pending_divorces.pop(d_key, None); return await ctx.reply("⌛ 已過期。")
        t_id, t_name = p["t_id"], p["t_name"]
        await self.db.execute("DELETE FROM marriages WHERE ((user1_id=? AND user2_id=?) OR (user1_id=? AND user2_id=?)) AND channel=?", (uid, t_id, t_id, uid, ch))
        self.pending_divorces.pop(d_key, None)
        await ctx.send(f"💔 {ctx.author.display_name} 與 {t_name} 緣分已盡。")

    @commands.command(name="運勢", aliases=["占卜", "fortune"])
    @commands.cooldown(1, 3, commands.Bucket.user)
    @safe_command
    async def cmd_fortune(self, ctx):
        today_str = datetime.datetime.now(LOCAL_TZ).strftime("%m/%d")
        f_title, f_desc = random.choices(FORTUNES_LIST, weights=[5, 20, 30, 25, 15, 5])[0]
        hair = random.choice(HAIR_STATUS_LIST)
        color = random.choice(COLORS_LIST)
        best_time = random.choice(TIMES_LIST)
        number = random.randint(0, 99)

        msg = f"📯 {today_str} 您的運勢占卜 | 運勢：{f_title} {f_desc} | 💆 台主頭髮狀態：{hair} | 🎨 幸運色：{color} | 🔢 幸運數字：{number} | ⏰ 幸運時段：{best_time}"
        await ctx.reply(msg)

    @commands.command(name='換分類', aliases=['更改分類', 'setgame'])
    @safe_command
    async def cmd_change_category(self, ctx, *, game_name: str = None):
        if not has_permission(ctx): return
        if not game_name: return await ctx.reply("❌ 請輸入要更換的分類名稱！例如：!換分類 XXX")
        await ctx.send(f"!game {game_name}")

    @commands.command(name='加指令', aliases=['acmd', 'newcmd'])
    @safe_command
    async def cmd_add_custom(self, ctx, cmd_name: str = None, *, reply_text: str = None):
        ok, ch, clean_cmd = await self._verify_custom_cmd_req(ctx, cmd_name)
        if not ok: return
        if not clean_cmd or not reply_text: return await ctx.reply("❌ 格式錯誤！範例：!acmd XXX...")

        await self.db.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", (f"CMD_{ch}_{clean_cmd}", reply_text))
        await ctx.reply(f"✅ 已新增自訂指令：!{clean_cmd}")

    @commands.command(name='刪指令', aliases=['dcmd', 'rmcmd'])
    @safe_command
    async def cmd_del_custom(self, ctx, cmd_name: str = None):
        ok, ch, clean_cmd = await self._verify_custom_cmd_req(ctx, cmd_name)
        if not ok: return
        if not clean_cmd: return await ctx.reply("❌ 請輸入要刪除的指令名稱！")

        if await self.db.execute("DELETE FROM bot_state WHERE key=?", (f"CMD_{ch}_{clean_cmd}",)) > 0:
            await ctx.reply(f"🗑️ 已刪除自訂指令：!{clean_cmd}")
        else:
            await ctx.reply(f"⚠️ 找不到該自訂指令。")

    @commands.command(name='查指令', aliases=['clist', 'lscmd'])
    @safe_command
    async def cmd_list_custom(self, ctx):
        ok, ch, _ = await self._verify_custom_cmd_req(ctx)
        if not ok: return

        rows = await self.db.fetchall("SELECT key FROM bot_state WHERE key LIKE ?", (f"CMD_{ch}_%",))
        if rows:
            cmds = [r[0].replace(f"CMD_{ch}_", "!") for r in rows]
            await ctx.reply(f"📜 本台自訂指令：{', '.join(cmds)}")
        else:
            await ctx.reply("📭 目前沒有任何自訂指令。")

    @commands.command(name='活躍榜', aliases=['top', '排行榜', '活躍排行榜'] + [f'top{i}' for i in range(1, 21)])
    @commands.cooldown(1, 10, commands.Bucket.channel)
    @safe_command
    async def cmd_top5_active(self, ctx, limit: str = "5"):
        if not has_permission(ctx): return
        ch = ctx.channel.name.lower()
        invoked = (getattr(ctx, "invoked_with", "") or "").lower()
        if not invoked:
            content = getattr(getattr(ctx, "message", None), "content", "") or ""
            invoked = content.split()[0].lstrip("!").lower() if content else ""
        if limit == "5":
            if m := re.fullmatch(r"top(\d{1,2})", invoked):
                limit = m.group(1)
        try:
            n = max(1, min(int(limit), 20))
        except ValueError:
            n = 5

        query = """
            SELECT user_id, watch_minutes, message_count, (watch_minutes * 2 + message_count * 5) as exp
            FROM user_stats
            WHERE channel=?
              AND user_id NOT IN (
                SELECT user_id FROM checkins WHERE LOWER(display_name)='chiwabots'
                UNION
                SELECT user_id FROM user_aliases WHERE LOWER(display_name)='chiwabots'
              )
            ORDER BY exp DESC
            LIMIT ?
        """
        rows = await self.db.fetchall(query, (ch, n))

        if not rows: return await ctx.reply("📭 目前本台還沒有任何觀眾數據紀錄喔！")

        user_data = []
        missing_ids = []

        for uid, w_mins, m_cnt, exp in rows:
            name_row = await self.db.fetchone("SELECT display_name FROM checkins WHERE user_id=? LIMIT 1", (uid,))
            if not name_row:
                name_row = await self.db.fetchone("SELECT display_name FROM user_aliases WHERE user_id=? LIMIT 1", (uid,))

            if name_row:
                dname = name_row[0]
            else:
                dname = None
                missing_ids.append(int(uid))

            user_data.append({"uid": uid, "dname": dname, "w_mins": w_mins, "m_cnt": m_cnt, "exp": exp})

        if missing_ids:
            try:
                api_users = await self.fetch_users(ids=missing_ids)
                api_name_map = {str(u.id): u.display_name for u in api_users}

                for item in user_data:
                    if item["dname"] is None:
                        found_name = api_name_map.get(item["uid"])
                        if found_name:
                            item["dname"] = found_name
                            await self.db.execute("INSERT OR REPLACE INTO user_aliases VALUES (?, ?, ?)", (item["uid"], found_name, datetime.datetime.now(LOCAL_TZ).isoformat()))
                        else:
                            item["dname"] = f"神秘人({item['uid'][-4:]})"
            except Exception as e:
                logging.error(f"API 查詢名字失敗: {e}")
                for item in user_data:
                    if item["dname"] is None: item["dname"] = f"神秘人({item['uid'][-4:]})"

        msg_parts = [f"🏆 本台活躍排行榜 (前{n}名)："]
        for i, data in enumerate(user_data):
            watch_str = self.format_watch_time(data["w_mins"])
            msg_parts.append(f"｜{i+1}. {data['dname']} (EXP:{int(data['exp'])}) 👀{watch_str} 💬{data['m_cnt']}")

        full_msg = "".join(msg_parts)
        await ctx.send(full_msg[:495] + "..." if len(full_msg) > 500 else full_msg)

    @commands.command(name='綁定VAL', aliases=['綁定val', 'bindval'])
    @commands.cooldown(1, 10, commands.Bucket.user)
    @require_general_admin
    async def cmd_bind_valorant(self, ctx, *, riot_id: str = None):
        if not riot_id or "#" not in riot_id:
            return await ctx.reply("⚠️ 請輸入正確格式：!綁定VAL 名字#TAG")
        riot_id = riot_id.strip()
        uid = self.broadcaster_name_map.get(ctx.channel.name.lower(), (None,))[0]
        if not uid:
            return await ctx.reply("⚠️ 無法取得台主資訊，請稍後再試")
        now = datetime.datetime.now(LOCAL_TZ).isoformat()
        await self.db.execute(
            "INSERT OR REPLACE INTO val_bindings (user_id, riot_id, bound_at) VALUES (?, ?, ?)",
            (uid, riot_id, now)
        )
        await ctx.reply(f"✅ 已綁定本頻道台主的 VALORANT 帳號：{riot_id}")

    @commands.command(name='rank', aliases=['rk', 'r', '牌位'])
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def cmd_valorant_rank(self, ctx, *, target: str = None):
        RANK_ZH = {
            "Iron": "鐵牌", "Bronze": "銅牌", "Silver": "銀牌", "Gold": "金牌",
            "Platinum": "白金", "Diamond": "鑽石", "Ascendant": "超凡入聖",
            "Immortal": "不朽", "Radiant": "輝煌"
        }
        RANK_EMOJI = {
            "Iron": "🪨", "Bronze": "🥉", "Silver": "🥈", "Gold": "🥇",
            "Platinum": "💠", "Diamond": "💎", "Ascendant": "🌿",
            "Immortal": "🔴", "Radiant": "⭐"
        }

        # 解析目標：@某人 / 名字#TAG / 空白（預設查台主）
        if target and "#" in target:
            riot_id = target.strip()
        else:
            if target:
                t = target.strip()
                if any(c in t for c in (' ', '/', '\\')) or len(t) > 30:
                    return await ctx.reply(f"⚠️ 格式錯誤，請用 @Twitch帳號 查綁定帳號，或 名字#TAG 直接查詢")
                lookup_uid, _, _ = await self.resolve_target(ctx, t)
                if not lookup_uid:
                    return await ctx.reply(f"⚠️ 找不到 Twitch 帳號 {t.replace('@', '')}，若要直接查詢請用 名字#TAG")
            else:
                lookup_uid = self.broadcaster_name_map.get(ctx.channel.name.lower(), (None,))[0]
            row = await self.db.fetchone("SELECT riot_id FROM val_bindings WHERE user_id=?", (lookup_uid,))
            if not row:
                who = "台主還沒有" if not target else f"{target.strip().replace('@', '')} 沒有"
                return await ctx.reply(f"⚠️ {who}綁定 VALORANT 帳號，請用 !綁定VAL 名字#TAG")
            riot_id = row[0]

        if "#" not in riot_id:
            return await ctx.reply("⚠️ 格式錯誤，請用 名字#TAG")

        name, tag = [x.strip() for x in riot_id.split("#", 1)]

        cache_key = f"rank:{name.lower()}#{tag.lower()}"
        cached = self._val_cache.get(cache_key)
        if cached and time.time() - cached[1] < 1800:
            return await ctx.reply(cached[0])

        url = f"https://api.henrikdev.xyz/valorant/v2/mmr/ap/{quote(name)}/{quote(tag)}"

        headers = {}
        if hdev_key := os.getenv("HENRIK_API_KEY"):
            headers["Authorization"] = hdev_key
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 404:
                        return await ctx.reply(f"⚠️ 查不到 {riot_id} 的牌位資料，可能是名稱錯誤，或本季尚未打過排位賽")
                    if r.status != 200:
                        return await ctx.reply(f"⚠️ API 錯誤 ({r.status})，請稍後再試")
                    data = (await r.json()).get("data", {})
        except Exception as e:
            logging.error(f"VALORANT rank API error: {e}")
            return await ctx.reply("⚠️ 無法取得牌位資訊，請稍後再試")

        current = data.get("current_data") or {}
        tier = current.get("currenttierpatched") or "Unranked"
        rr = current.get("ranking_in_tier", 0)
        rr_change = current.get("mmr_change_to_last_game")
        elo = current.get("elo")
        peak = data.get("highest_rank", {})
        peak_tier = peak.get("patched_tier", "")

        def to_zh(t):
            for en, zh in RANK_ZH.items():
                if en in t:
                    num = t.replace(en, "").strip()
                    return f"{zh} {num}".strip() if num else zh
            return t

        emoji = next((v for k, v in RANK_EMOJI.items() if k in tier), "🎮")
        tier_zh = to_zh(tier)
        peak_zh = to_zh(peak_tier)
        change_str = f" ({'+' if rr_change and rr_change > 0 else ''}{rr_change} 上局)" if rr_change is not None else ""
        elo_str = f" | 隱分 {elo}" if elo else ""
        peak_str = f" | 🏆 最高：{peak_zh}" if peak_tier and peak_tier != tier else ""

        actual_name = data.get("name") or name
        actual_tag = data.get("tag") or tag
        display_id = f"{actual_name}#{actual_tag}"
        msg = f"【{display_id}】 {emoji} {tier_zh} | {rr} RR{change_str}{elo_str}{peak_str}"
        self._val_cache[cache_key] = (msg, time.time())
        await ctx.reply(msg)

    @commands.command(name='最近對戰', aliases=['近況', 'matches'])
    @commands.cooldown(1, 5, commands.Bucket.user)
    @safe_command
    async def cmd_val_matches(self, ctx, *, target: str = None):
        # 解析目標
        if target and "#" in target:
            riot_id = target.strip()
            name, tag = [x.strip() for x in riot_id.split("#", 1)]
        else:
            if target:
                t = target.strip()
                if any(c in t for c in (' ', '/', '\\')) or len(t) > 30:
                    return await ctx.reply(f"⚠️ 格式錯誤，請用 @Twitch帳號 查綁定帳號，或 名字#TAG 直接查詢")
                lookup_uid, _, _ = await self.resolve_target(ctx, t)
                if not lookup_uid:
                    return await ctx.reply(f"⚠️ 找不到 Twitch 帳號 {t.replace('@', '')}，若要直接查詢請用 名字#TAG")
            else:
                lookup_uid = self.broadcaster_name_map.get(ctx.channel.name.lower(), (None,))[0]
            row = await self.db.fetchone("SELECT riot_id FROM val_bindings WHERE user_id=?", (lookup_uid,))
            if not row:
                who = "台主還沒有" if not target else f"{target.strip().replace('@', '')} 沒有"
                return await ctx.reply(f"⚠️ {who}綁定 VALORANT 帳號，請用 !綁定VAL 名字#TAG")
            riot_id = row[0]
            name, tag = [x.strip() for x in riot_id.split("#", 1)]

        AGENT_ZH = {
            "Brimstone": "硫磺石", "Viper": "蛇影", "Omen": "惡兆", "Killjoy": "殺喜",
            "Cypher": "密探", "Sova": "索娃", "Sage": "聖者", "Phoenix": "鳳凰",
            "Jett": "捷特", "Reyna": "雷娜", "Raze": "蕾茲", "Breach": "突破者",
            "Skye": "斯凱", "Yoru": "夜路", "Astra": "星靈", "KAY/O": "KAY/O",
            "Chamber": "商會", "Neon": "霓虹", "Fade": "費德", "Harbor": "海灣",
            "Gekko": "蓋可", "Deadlock": "死鎖", "Iso": "依索", "Clove": "丁香",
            "Vyse": "薇絲", "Tejo": "特何", "Waylay": "截擊"
        }
        MAP_ZH = {
            "Bind": "綁定", "Haven": "天堂", "Split": "裂縫", "Ascent": "巔峰",
            "Icebox": "冰原", "Breeze": "微風", "Fracture": "斷裂", "Pearl": "珍珠",
            "Lotus": "蓮花", "Sunset": "夕陽", "Abyss": "深淵"
        }
        MODE_ZH = {
            "competitive": "天梯", "unrated": "普通", "spikerush": "急速",
            "deathmatch": "死鬥", "teamdeathmatch": "小隊死鬥", "escalation": "升級",
            "replication": "複製", "custom": "自訂", "premier": "菁英聯賽",
            "hurm": "超英模式", "newmap": "新地圖"
        }

        cache_key = f"matches:{name.lower()}#{tag.lower()}"
        cached = self._val_cache.get(cache_key)
        if cached and time.time() - cached[1] < 1800:
            return await ctx.reply(cached[0])

        url = f"https://api.henrikdev.xyz/valorant/v3/matches/ap/{quote(name)}/{quote(tag)}?size=3"
        headers = {}
        if hdev_key := os.getenv("HENRIK_API_KEY"):
            headers["Authorization"] = hdev_key

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status == 404:
                        return await ctx.reply(f"⚠️ 找不到玩家 {riot_id}")
                    if r.status != 200:
                        raw = await r.text()
                        logging.error(f"VAL matches API {r.status}: {raw[:300]}")
                        return await ctx.reply(f"⚠️ API 錯誤 ({r.status})，請稍後再試")
                    matches = (await r.json(content_type=None)).get("data", [])
        except Exception as e:
            logging.exception(f"VAL matches API error: {type(e).__name__}: {e}")
            return await ctx.reply("⚠️ 無法取得對戰紀錄，請稍後再試")

        if not matches:
            return await ctx.reply(f"⚠️ {riot_id} 近期沒有天梯對戰紀錄")

        parts = []
        for m in matches:
            try:
                meta = m.get("metadata", {})
                map_name = meta.get("map", "?")
                rounds = meta.get("rounds_played", 0)
                mode_raw = meta.get("mode", "").lower().replace(" ", "")
                mode = MODE_ZH.get(mode_raw, mode_raw or "?")

                # 找自己的資料
                player = next(
                    (p for p in m.get("players", {}).get("all_players", [])
                     if p.get("name", "").lower() == name.lower() and p.get("tag", "").lower() == tag.lower()),
                    None
                )
                if not player:
                    continue

                stats = player.get("stats", {})
                k, d, a = stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)
                hs = stats.get("headshots", 0)
                bs = stats.get("bodyshots", 0)
                ls = stats.get("legshots", 0)
                total_shots = hs + bs + ls
                hs_pct = round(hs / total_shots * 100) if total_shots > 0 else 0
                team = player.get("team", "").lower()
                agent_en = player.get("character", "?")
                agent = AGENT_ZH.get(agent_en, agent_en)
                map_name = MAP_ZH.get(map_name, map_name)

                team_data = m.get("teams", {}).get(team, {})
                has_won = team_data.get("has_won")
                result = "✅" if has_won is True else "❌" if has_won is False else "▪️"

                parts.append(f"{result}[{mode}]{agent}/{map_name} {k}/{d}/{a} HS{hs_pct}%")
            except Exception:
                continue

        if not parts:
            return await ctx.reply(f"⚠️ 無法解析對戰資料")

        msg = f"【{riot_id}】 近{len(parts)}場：" + " | ".join(parts)
        msg = msg[:495] + "..." if len(msg) > 500 else msg
        self._val_cache[cache_key] = (msg, time.time())
        await ctx.reply(msg)

# ==============================================================================
# [8] 主程式啟動區
# ==============================================================================
if __name__ == "__main__":
    force_cleanup_zombies()

    bot = Bot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logging.info("🛑 收到手動終止指令 (Ctrl+C)，正在安全清理並關閉系統...")
        force_cleanup_zombies()
        sys.exit(0)

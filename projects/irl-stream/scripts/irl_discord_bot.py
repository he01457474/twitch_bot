#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IRL 中繼 Discord 指令監聽 — /狀態 查詢中繼狀態。

跟私人秘書 bot 同一套：slash command（app_commands.CommandTree）+ .env 設定。
收到 /狀態 時觸發 status_irl.ps1 -ToDiscord，把狀態透過管理員通知 webhook 貼到 Discord。

設定檔：../.env（IRL_DISCORD_TOKEN、IRL_MAIN_GUILD_ID）
由 stream_start.ps1 背景帶起，stream_stop.ps1 依 PID 關閉。
"""
import os
import asyncio
import logging
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent          # projects/irl-stream
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / '.env'
STATUS_PS1 = SCRIPT_DIR / 'status_irl.ps1'
PID_FILE = Path(os.environ.get('TEMP', str(SCRIPT_DIR))) / 'irl_discord_bot.pid'

load_dotenv(ENV_FILE)

DISCORD_TOKEN = os.getenv('IRL_DISCORD_TOKEN', '').strip()
MAIN_GUILD_ID = int(os.getenv('IRL_MAIN_GUILD_ID', '0') or '0')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('irl-discord')

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


def _guild_allowed(guild_id: int) -> bool:
    """未設定 IRL_MAIN_GUILD_ID 時全部允許；設定後只允許該伺服器。"""
    return (not MAIN_GUILD_ID) or (guild_id == MAIN_GUILD_ID)


@bot.event
async def on_ready():
    for guild in bot.guilds:
        if not _guild_allowed(guild.id):
            continue
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            log.info(f'指令已同步到伺服器：{guild.name}')
        except Exception as exc:
            log.warning(f'伺服器 {guild.name} 同步失敗: {exc}')
    tree.clear_commands(guild=None)
    await tree.sync()
    log.info(f'IRL Discord 指令監聽已上線：{bot.user}')


@tree.command(name='狀態', description='查詢 IRL 中繼目前狀態（伺服器 / 推流 / 白名單 / DDNS）')
async def cmd_status(interaction: discord.Interaction):
    if not _guild_allowed(interaction.guild_id or 0):
        await interaction.response.send_message('此伺服器未啟用 IRL 查詢。', ephemeral=True)
        return
    await interaction.response.send_message('查詢中，狀態會貼到通知頻道…', ephemeral=True)
    try:
        proc = await asyncio.create_subprocess_exec(
            'powershell', '-ExecutionPolicy', 'Bypass', '-NoProfile',
            '-File', str(STATUS_PS1), '-ToDiscord',
            cwd=str(SCRIPT_DIR),
        )
        await proc.wait()
    except Exception as exc:
        log.warning(f'查詢失敗: {exc}')


def main():
    if not DISCORD_TOKEN:
        log.error('IRL_DISCORD_TOKEN 未設定，請編輯 projects/irl-stream/.env 或跑「設定Discord指令.bat」。')
        return
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


if __name__ == '__main__':
    main()

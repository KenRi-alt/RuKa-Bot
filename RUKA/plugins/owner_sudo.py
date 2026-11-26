import os, sys, time, shutil, asyncio, traceback, importlib.metadata
from io import StringIO
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from RUKA import CONFIG
from RUKA.utils.db import get_pool, get_user_stats, update_user_stats

router = Router()
START_TIME = time.time()
GBANNED_USERS: set[int] = set()
MAINTENANCE_MODE = False


def is_owner(uid: int) -> bool:
    return uid in (CONFIG.OWNER_LIST or [])


def is_dev(uid: int) -> bool:
    return is_owner(uid) or uid in (CONFIG.DEV_LIST or [])


def is_sudo(uid: int) -> bool:
    return is_dev(uid) or uid in (CONFIG.SUDO_LIST or [])


def get_uptime() -> str:
    s = int(time.time() - START_TIME)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return f"{d}d {h}h {m}m {s}s"


def _uid_amt(message: Message) -> tuple[int | None, int | None]:
    p = message.text.split()
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
        return uid, (int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else None)
    if len(p) >= 3 and p[1].lstrip("-").isdigit() and p[2].lstrip("-").isdigit():
        return int(p[1]), int(p[2])
    if len(p) == 2 and p[1].lstrip("-").isdigit():
        return int(p[1]), None
    return None, None


# --- 1–6: System, API & Diagnostics ---
@router.message(Command("stats", prefix="/!"))
async def bot_stats(message: Message):
    if not is_sudo(message.from_user.id): return
    await message.answer(
        f"📊 **RuKa-Bot Stats**\n• Uptime: `{get_uptime()}`\n• Python: `{sys.version.split()[0]}`\n"
        f"• Owners: `{len(CONFIG.OWNER_LIST)}` | Devs: `{len(CONFIG.DEV_LIST)}` | Sudos: `{len(CONFIG.SUDO_LIST)}`"
    )


@router.message(Command("apihealth", "devconfig", prefix="/!"))
async def api_health(message: Message):
    if not is_dev(message.from_user.id): return
    t0 = time.time()
    me = await message.bot.get_me()
    api_ms = round((time.time() - t0) * 1000, 2)
    api_id_ok = "✅ Valid" if isinstance(CONFIG.API_ID, int) and CONFIG.API_ID > 0 else "❌ Invalid"
    api_hash_ok = f"✅ Set (`{CONFIG.API_HASH[:4]}...{CONFIG.API_HASH[-4:]}`)" if CONFIG.API_HASH and len(CONFIG.API_HASH) == 32 else "❌ Invalid"
    await message.answer(
        f"🔌 **API & Credentials Health**\n\n"
        f"• **API_ID:** {api_id_ok} (`{CONFIG.API_ID}`)\n"
        f"• **API_HASH:** {api_hash_ok}\n"
        f"• **Bot API Ping:** `{api_ms}ms` (`@{me.username}`)\n"
        f"• **GROQ_API_KEY:** {'✅ Set' if os.getenv('GROQ_API_KEY') else '❌ Missing'}"
    )


@router.message(Command("sysinfo", prefix="/!"))
async def sys_info_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    total, used, free = shutil.disk_usage("/")
    await message.answer(
        f"🖥️ **Server Diagnostics**\n"
        f"• OS: `{os.name}` | CPUs: `{os.cpu_count()}`\n"
        f"• Disk: `{used // (1024**3)}GB / {total // (1024**3)}GB` (`{free // (1024**3)}GB free`)\n"
        f"• Uptime: `{get_uptime()}`"
    )


@router.message(Command("pipcheck", prefix="/!"))
async def pip_check_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    pkgs = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    await message.answer("📦 **Installed Packages:**\n```\n" + "\n".join(pkgs[:30]) + "\n```")


@router.message(Command("testdb", prefix="/!"))
async def test_db_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    t0 = time.time()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    await message.answer(f"🗄️ **PostgreSQL Ping:** `{round((time.time() - t0) * 1000, 2)}ms` ✅")


@router.message(Command("env", prefix="/!"))
async def env_check_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    keys = ["BOT_TOKEN", "API_ID", "API_HASH", "DB_URL", "GROQ_API_KEY", "LOGS_CHANNEL", "SUPPORT_CHAT_ID"]
    await message.answer("🔐 **Env Status:**\n" + "\n".join(f"• `{k}`: {'✅' if os.getenv(k) else '❌'}" for k in keys))


# --- 7–13: Live Telegram Bot Profile & Menu Management ---
@router.message(Command("setbotcmds", prefix="/!"))
async def set_bot_cmds(message: Message):
    if not is_dev(message.from_user.id): return
    cmds = [
        BotCommand(command="start", description="Start Ruka"),
        BotCommand(command="help", description="Command Guide"),
        BotCommand(command="ruka", description="Chat with Ruka AI"),
        BotCommand(command="gacha", description="Pull Waifu/Husbando card"),
        BotCommand(command="shop", description="Open Ruka's Shop"),
        BotCommand(command="daily", description="Claim daily coins"),
        BotCommand(command="rank", description="View your Trainer Card"),
        BotCommand(command="settings", description="Group security settings"),
    ]
    await message.bot.set_my_commands(cmds)
    await message.answer("✅ Updated Telegram `/` Command Menu!")


@router.message(Command("clearbotcmds", prefix="/!"))
async def clear_bot_cmds(message: Message):
    if not is_dev(message.from_user.id): return
    await message.bot.delete_my_commands()
    await message.answer("🗑️ Cleared Telegram `/` Command Menu!")


@router.message(Command("setbotname", prefix="/!"))
async def set_bot_name(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/setbotname Ruka Sarashina`")
    await message.bot.set_my_name(p[1][:64])
    await message.answer(f"✅ Bot name updated to **{p[1][:64]}**!")


@router.message(Command("setbotdesc", prefix="/!"))
async def set_bot_desc(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/setbotdesc <description>`")
    await message.bot.set_my_description(p[1][:512])
    await message.answer("✅ Bot description updated!")


@router.message(Command("setbotshort", prefix="/!"))
async def set_bot_short(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/setbotshort <short bio>`")
    await message.bot.set_my_short_description(p[1][:120])
    await message.answer("✅ Bot short bio updated!")


@router.message(Command("webhookinfo", prefix="/!"))
async def webhook_info(message: Message):
    if not is_dev(message.from_user.id): return
    info = await message.bot.get_webhook_info()
    await message.answer(f"🌐 **Webhook Info:**\n• URL: `{info.url or 'Polling'}`\n• Pending Updates: `{info.pending_update_count}`")


@router.message(Command("flushupdates", prefix="/!"))
async def flush_updates(message: Message):
    if not is_dev(message.from_user.id): return
    await message.bot.delete_webhook(drop_pending_updates=True)
    await message.answer("🧹 Flushed all pending Telegram updates!")


# --- 14–18: Hierarchy Management ---
@router.message(Command("sudolist", prefix="/!"))
async def sudo_list_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    await message.answer(f"👑 **Owners:** `{CONFIG.OWNER_LIST}`\n🛠️ **Devs:** `{CONFIG.DEV_LIST}`\n⚡ **Sudos:** `{CONFIG.SUDO_LIST}`")


@router.message(Command("addsudo", "rmsudo", "adddev", "rmdev", prefix="/!"))
async def hierarchy_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    uid, _ = _uid_amt(message)
    if not uid: return await message.answer("Reply or pass User ID!")
    target_list = CONFIG.SUDO_LIST if "sudo" in cmd else CONFIG.DEV_LIST
    if cmd.startswith("add") and uid not in target_list:
        target_list.append(uid); await message.answer(f"✅ Added `{uid}` (`{cmd}`)!")
    elif cmd.startswith("rm") and uid in target_list:
        target_list.remove(uid); await message.answer(f"🗑️ Removed `{uid}` (`{cmd}`)!")


# --- 19–25: Economy & Database God Controls ---
@router.message(Command("addcoins", "rmcoins", "addxp", prefix="/!"))
async def god_economy(message: Message):
    if not is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    uid, amt = _uid_amt(message)
    if not uid or amt is None: return await message.answer(f"Usage: `/{cmd} <amount>` (reply) or `/{cmd} <id> <amount>`")
    if cmd == "addcoins": await update_user_stats(uid, coins=amt)
    elif cmd == "rmcoins": await update_user_stats(uid, coins=-abs(amt))
    else: await update_user_stats(uid, xp=amt)
    s = await get_user_stats(uid)
    await message.answer(f"💎 Updated `{uid}` → Coins: `{s['coins']}` | XP: `{s['xp']}`")


@router.message(Command("giveallcoins", "giveallxp", prefix="/!"))
async def airdrop_all(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split()
    if len(p) < 2 or not p[1].isdigit(): return await message.answer("Usage: `/giveallcoins 500`")
    amt = int(p[1])
    col = "coins" if "coins" in message.text.lower() else "xp"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE user_stats SET {col} = {col} + $1", amt)
    await message.answer(f"🎉 **Airdrop!** Granted `+{amt} {col}` to ALL users in database!")


@router.message(Command("toprich", prefix="/!"))
async def top_rich_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, coins FROM user_stats ORDER BY coins DESC LIMIT 10")
    await message.answer("💰 **Top 10 Richest:**\n" + "\n".join(f"• `{r['user_id']}`: `{r['coins']} 💎`" for r in rows))


@router.message(Command("resetuser", prefix="/!"))
async def reset_user_god(message: Message):
    if not is_owner(message.from_user.id): return
    uid, _ = _uid_amt(message)
    if not uid: return
    pool = await get_pool()
    async with pool.acquire() as conn: await conn.execute("UPDATE user_stats SET coins=100, xp=0 WHERE user_id=$1", uid)
    await message.answer(f"🔄 Reset `{uid}` to `100 💎` & `0 XP`!")


@router.message(Command("dbstats", prefix="/!"))
async def db_stats_cmd(message: Message):
    if not is_sudo(message.from_user.id): return
    pool = await get_pool()
    async with pool.acquire() as conn:
        u = await conn.fetchval("SELECT COUNT(*) FROM user_stats")
        c = await conn.fetchval("SELECT COUNT(*) FROM chat_settings")
        g = await conn.fetchval("SELECT COUNT(*) FROM gacha_collection")
        m = await conn.fetchval("SELECT COUNT(*) FROM marriage_data")
    await message.answer(f"🗄️ **DB Stats:** Users: `{u}` | Groups: `{c}` | Cards: `{g}` | Marriages: `{m}`")


@router.message(Command("sql", prefix="/!"))
async def sql_exec_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            if p[1].strip().lower().startswith("select"):
                rows = await conn.fetch(p[1])
                out = "\n".join(str(dict(r)) for r in rows[:20]) or "No rows."
            else:
                out = f"✅ {await conn.execute(p[1])}"
    except Exception as e:
        out = f"❌ {e}"
    await message.answer(f"```\n{out[:3800]}\n```")


@router.message(Command("wipechat", prefix="/!"))
async def wipe_chat_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split()
    cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
    pool = await get_pool()
    async with pool.acquire() as conn:
        for tbl in ("chat_settings", "chat_filters", "approved_users", "chat_locks", "chat_blacklists"):
            await conn.execute(f"DELETE FROM {tbl} WHERE chat_id=$1", cid)
    await message.answer(f"🧹 Wiped all data for `{cid}`!")


# --- 26–33: Global Bans, Send, Leave, Eval, Shell, Restart ---
@router.message(Command("gban", "ungban", "gbanlist", prefix="/!"))
async def gban_cmds(message: Message):
    if not is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "gbanlist":
        return await message.answer("🌐 **GBanned:** " + ", ".join(map(str, GBANNED_USERS)) if GBANNED_USERS else "None.")
    uid, _ = _uid_amt(message)
    if not uid: return
    if cmd == "gban":
        GBANNED_USERS.add(uid); await message.answer(f"🌐 **GBanned** `{uid}`!")
    else:
        GBANNED_USERS.discard(uid); await message.answer(f"🌸 **UnGBanned** `{uid}`!")


@router.message(Command("send", prefix="/!"))
async def send_as_bot(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 2)
    if len(p) >= 3:
        await message.bot.send_message(int(p[1]), p[2])
        await message.answer(f"✅ Sent to `{p[1]}`!")


@router.message(Command("leavechat", prefix="/!"))
async def leave_chat_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split()
    cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
    await message.bot.leave_chat(cid)


@router.message(Command("eval", prefix="/!"))
async def eval_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return
    old = sys.stdout; sys.stdout = out_io = StringIO()
    try:
        exec("async def __a(message):\n" + "\n".join(f"    {l}" for l in p[1].splitlines()), globals(), locals())
        await locals()["__a"](message)
        out = out_io.getvalue() or "✅ Done."
    except Exception:
        out = traceback.format_exc()
    finally:
        sys.stdout = old
    await message.answer(f"```python\n{out[:3800]}\n```")


@router.message(Command("sh", "bash", prefix="/!"))
async def shell_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return
    proc = await asyncio.create_subprocess_shell(p[1], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    so, se = await proc.communicate()
    await message.answer(f"```bash\n{(so.decode() + se.decode()).strip()[:3800] or '✅ Done.'}\n```")


@router.message(Command("restart", prefix="/!"))
async def restart_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    await message.answer("🔄 **Restarting RuKa-Bot...** 💓")
    os.execv(sys.executable, [sys.executable] + sys.argv)
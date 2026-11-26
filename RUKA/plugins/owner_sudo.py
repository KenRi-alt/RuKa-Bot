import os
import sys
import time
import asyncio
import traceback
from io import StringIO
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from RUKA import CONFIG
from RUKA.utils.db import get_pool, get_user_stats, update_user_stats

router = Router()
START_TIME = time.time()
GBANNED_USERS: set[int] = set()


def is_owner(uid: int) -> bool:
    return uid in (CONFIG.OWNER_LIST or [])


def is_sudo(uid: int) -> bool:
    return (
        uid in (CONFIG.OWNER_LIST or [])
        or uid in (CONFIG.DEV_LIST or [])
        or uid in (CONFIG.SUDO_LIST or [])
    )


def get_uptime() -> str:
    secs = int(time.time() - START_TIME)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h {mins}m {secs}s"


def _extract_uid_and_amt(message: Message) -> tuple[int | None, int | None]:
    parts = message.text.split()
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
        amt = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else None
        return uid, amt
    if len(parts) >= 3 and parts[1].lstrip("-").isdigit() and parts[2].lstrip("-").isdigit():
        return int(parts[1]), int(parts[2])
    if len(parts) == 2 and parts[1].lstrip("-").isdigit():
        return int(parts[1]), None
    return None, None


# --- 1–4: System & Bot Info ---
@router.message(Command("stats", prefix="/!"))
async def bot_stats(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    await message.answer(
        f"📊 **RuKa-Bot System Stats**\n\n"
        f"⏱️ **Uptime:** `{get_uptime()}`\n"
        f"🐍 **Python:** `{sys.version.split()[0]}`\n"
        f"👑 **Owners:** `{len(CONFIG.OWNER_LIST)}`\n"
        f"🛠️ **Devs:** `{len(CONFIG.DEV_LIST)}`\n"
        f"⚡ **Sudos:** `{len(CONFIG.SUDO_LIST)}`"
    )


@router.message(Command("botinfo", prefix="/!"))
async def bot_info_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    me = await message.bot.get_me()
    await message.answer(
        f"🤖 **Bot Identity**\n"
        f"• Name: `{me.full_name}`\n"
        f"• Username: `@{me.username}`\n"
        f"• ID: `{me.id}`\n"
        f"• Uptime: `{get_uptime()}`"
    )


@router.message(Command("env", prefix="/!"))
async def env_check_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    keys = ["BOT_TOKEN", "DB_URL", "GROQ_API_KEY", "GROK_API_KEY", "LOGS_CHANNEL", "SUPPORT_CHAT_ID"]
    lines = ["🔐 **Environment Status:**\n"]
    for k in keys:
        val = os.getenv(k)
        lines.append(f"• `{k}`: {'✅ Set' if val else '❌ Missing'}")
    await message.answer("\n".join(lines))


@router.message(Command("sudolist", prefix="/!"))
async def sudo_list_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    await message.answer(
        f"👑 **RuKa-Bot Hierarchy**\n\n"
        f"**Owners:** `{CONFIG.OWNER_LIST}`\n"
        f"**Devs:** `{CONFIG.DEV_LIST}`\n"
        f"**Sudos:** `{CONFIG.SUDO_LIST}`"
    )


# --- 5–8: Hierarchy Management (/addsudo, /rmsudo, /adddev, /rmdev) ---
@router.message(Command("addsudo", prefix="/!"))
async def add_sudo(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid not in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.append(uid)
    await message.answer(f"⚡ Added `{uid}` to **SUDO_LIST**!")


@router.message(Command("rmsudo", prefix="/!"))
async def rm_sudo(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.remove(uid)
    await message.answer(f"🗑️ Removed `{uid}` from **SUDO_LIST**!")


@router.message(Command("adddev", prefix="/!"))
async def add_dev(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid not in CONFIG.DEV_LIST:
        CONFIG.DEV_LIST.append(uid)
    await message.answer(f"🛠️ Promoted `{uid}` to **DEV_LIST**!")


@router.message(Command("rmdev", prefix="/!"))
async def rm_dev(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid in CONFIG.DEV_LIST:
        CONFIG.DEV_LIST.remove(uid)
    await message.answer(f"🗑️ Removed `{uid}` from **DEV_LIST**!")


# --- 9–12: Economy & XP God Controls (/addcoins, /rmcoins, /addxp, /resetuser) ---
@router.message(Command("addcoins", prefix="/!"))
async def add_coins_god(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, amt = _extract_uid_and_amt(message)
    if not uid or amt is None:
        return await message.answer("Usage: `/addcoins <amount>` (reply) or `/addcoins <user_id> <amount>`")
    await update_user_stats(uid, coins=amt)
    stats = await get_user_stats(uid)
    await message.answer(f"💎 Spawned **`{amt}` Coins** for `{uid}`!\nNew Balance: `{stats['coins']} 💎`")


@router.message(Command("rmcoins", prefix="/!"))
async def rm_coins_god(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, amt = _extract_uid_and_amt(message)
    if not uid or amt is None:
        return await message.answer("Usage: `/rmcoins <amount>` (reply) or `/rmcoins <user_id> <amount>`")
    await update_user_stats(uid, coins=-abs(amt))
    stats = await get_user_stats(uid)
    await message.answer(f"💸 Deducted **`{amt}` Coins** from `{uid}`!\nNew Balance: `{stats['coins']} 💎`")


@router.message(Command("addxp", prefix="/!"))
async def add_xp_god(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, amt = _extract_uid_and_amt(message)
    if not uid or amt is None:
        return await message.answer("Usage: `/addxp <amount>` (reply) or `/addxp <user_id> <amount>`")
    await update_user_stats(uid, xp=amt)
    stats = await get_user_stats(uid)
    await message.answer(f"✨ Granted **`{amt}` XP** to `{uid}`!\nTotal XP: `{stats['xp']}`")


@router.message(Command("resetuser", prefix="/!"))
async def reset_user_god(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE user_stats SET coins=100, xp=0 WHERE user_id=$1", uid)
    await message.answer(f"🔄 Reset `{uid}` back to `100 💎` and `0 XP`!")


# --- 13–15: PostgreSQL God Controls (/dbstats, /sql, /wipechat) ---
@router.message(Command("dbstats", prefix="/!"))
async def db_stats_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    pool = await get_pool()
    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM user_stats")
        chats = await conn.fetchval("SELECT COUNT(*) FROM chat_settings")
        cards = await conn.fetchval("SELECT COUNT(*) FROM gacha_collection")
        marriages = await conn.fetchval("SELECT COUNT(*) FROM marriage_data")
        feds = await conn.fetchval("SELECT COUNT(*) FROM federations")
    await message.answer(
        f"🗄️ **PostgreSQL Live Stats**\n\n"
        f"• Users: `{users}`\n"
        f"• Groups: `{chats}`\n"
        f"• Gacha Cards: `{cards}`\n"
        f"• Marriages: `{marriages}`\n"
        f"• Federations: `{feds}`"
    )


@router.message(Command("sql", prefix="/!"))
async def sql_exec_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/sql SELECT * FROM user_stats LIMIT 5;`")
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            if parts[1].strip().lower().startswith("select"):
                rows = await conn.fetch(parts[1])
                out = "\n".join(str(dict(r)) for r in rows[:20]) or "No rows."
            else:
                res = await conn.execute(parts[1])
                out = f"✅ Executed: `{res}`"
    except Exception as e:
        out = f"❌ SQL Error:\n{e}"
    await message.answer(f"```\n{out[:3800]}\n```")


@router.message(Command("wipechat", prefix="/!"))
async def wipe_chat_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split()
    cid = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else message.chat.id
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_settings WHERE chat_id=$1", cid)
        await conn.execute("DELETE FROM chat_filters WHERE chat_id=$1", cid)
        await conn.execute("DELETE FROM approved_users WHERE chat_id=$1", cid)
    await message.answer(f"🧹 Wiped all settings, filters & approvals for `{cid}`!")


# --- 16–18: Global Bans (/gban, /ungban, /gbanlist) ---
@router.message(Command("gban", prefix="/!"))
async def gban_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply or pass ID to **GBan**!")
    GBANNED_USERS.add(uid)
    if CONFIG.GBAN_LOGS:
        try:
            await message.bot.send_message(CONFIG.GBAN_LOGS, f"🌐 **GBAN**\nUser: `{uid}`\nBy: {message.from_user.full_name}", parse_mode=None)
        except Exception:
            pass
    await message.answer(f"🌐 **Globally Banned** `{uid}`!")


@router.message(Command("ungban", prefix="/!"))
async def ungban_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    uid, _ = _extract_uid_and_amt(message)
    if not uid:
        return await message.answer("Reply or pass ID to **UnGBan**!")
    GBANNED_USERS.discard(uid)
    await message.answer(f"🌸 **Globally Unbanned** `{uid}`!")


@router.message(Command("gbanlist", prefix="/!"))
async def gban_list_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    await message.answer("🌐 **GBanned Users:**\n" + "\n".join(f"• `{u}`" for u in GBANNED_USERS) if GBANNED_USERS else "No GBanned users.")


# --- 19–23: Remote Messaging, Eval, Shell & Restart ---
@router.message(Command("send", prefix="/!"))
async def send_as_bot(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/send <chat_id> <text>`")
    await message.bot.send_message(int(parts[1]), parts[2])
    await message.answer(f"✅ Sent message to `{parts[1]}`!")


@router.message(Command("leavechat", prefix="/!"))
async def leave_chat_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split()
    cid = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else message.chat.id
    await message.bot.leave_chat(cid)
    if cid != message.chat.id:
        await message.answer(f"👋 Left chat `{cid}`!")


@router.message(Command("eval", prefix="/!"))
async def eval_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Give me Python code to run!")
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    try:
        exec(
            "async def __aexec(message):\n" + "\n".join(f"    {line}" for line in parts[1].splitlines()),
            globals(),
            locals()
        )
        await locals()["__aexec"](message)
        out = mystdout.getvalue() or "✅ Executed (no output)."
    except Exception:
        out = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
    await message.answer(f"```python\n{out[:3800]}\n```")


@router.message(Command("sh", "bash", prefix="/!"))
async def shell_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/sh <command>`")
    proc = await asyncio.create_subprocess_shell(parts[1], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    out = (stdout.decode() + stderr.decode()).strip() or "✅ Done."
    await message.answer(f"```bash\n{out[:3800]}\n```")


@router.message(Command("restart", prefix="/!"))
async def restart_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    await message.answer("🔄 **Restarting RuKa-Bot...** 💓")
    os.execv(sys.executable, [sys.executable] + sys.argv)
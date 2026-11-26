import os, sys, time, shutil, asyncio, traceback, importlib.metadata
from io import StringIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA import CONFIG
from RUKA.utils.db import get_pool, get_user_stats, update_user_stats

router = Router()
START_TIME = time.time()
GBANNED_USERS: set[int] = set()


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


def _owner_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 API Health", callback_data="own_api"),
         InlineKeyboardButton(text="🗄️ DB Stats", callback_data="own_db")],
        [InlineKeyboardButton(text="🖥️ Server Specs", callback_data="own_sys"),
         InlineKeyboardButton(text="📋 Set `/` Menu", callback_data="own_cmds")],
        [InlineKeyboardButton(text="🧹 Flush Queue", callback_data="own_flush"),
         InlineKeyboardButton(text="🔄 Restart Bot", callback_data="own_restart")],
        [InlineKeyboardButton(text="❌ Close", callback_data="own_close")],
    ])


# --- 1. Interactive /ownerpanel (UI/UX Control Center) ---
@router.message(Command("ownerpanel", "devpanel", prefix="/!"))
async def owner_panel_cmd(message: Message):
    if not is_dev(message.from_user.id):
        return await message.answer("❌ Owner/Dev only!")
    await message.answer(
        f"👑 **Ruka God-Mode Control Center**\n"
        f"⏱️ Uptime: `{get_uptime()}`\n\n"
        f"Select a diagnostic or management action below:",
        reply_markup=_owner_panel_markup()
    )


@router.callback_query(F.data.startswith("own_"))
async def owner_panel_cb(query: CallbackQuery):
    if not is_dev(query.from_user.id):
        return await query.answer("❌ Owner/Dev only!", show_alert=True)
    act = query.data.split("_")[1]
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="own_back")]])

    if act == "close":
        return await query.message.delete()
    if act == "back":
        return await query.message.edit_text(
            f"👑 **Ruka God-Mode Control Center**\n⏱️ Uptime: `{get_uptime()}`",
            reply_markup=_owner_panel_markup()
        )
    if act == "api":
        t0 = time.time(); me = await query.bot.get_me(); ms = round((time.time() - t0) * 1000, 2)
        h_mask = f"{CONFIG.API_HASH[:4]}...{CONFIG.API_HASH[-4:]}" if CONFIG.API_HASH else "Missing"
        await query.message.edit_text(
            f"🔌 **API & Secrets Health**\n"
            f"• API_ID: `{CONFIG.API_ID}`\n• API_HASH: `{h_mask}`\n"
            f"• Bot: `@{me.username}` (`{ms}ms`)\n• Groq Key: {'✅' if os.getenv('GROQ_API_KEY') else '❌'}",
            reply_markup=back
        )
    elif act == "db":
        t0 = time.time(); pool = await get_pool()
        async with pool.acquire() as conn:
            u = await conn.fetchval("SELECT COUNT(*) FROM user_stats")
            c = await conn.fetchval("SELECT COUNT(*) FROM chat_settings")
            g = await conn.fetchval("SELECT COUNT(*) FROM gacha_collection")
            m = await conn.fetchval("SELECT COUNT(*) FROM marriage_data")
        ms = round((time.time() - t0) * 1000, 2)
        await query.message.edit_text(
            f"🗄️ **PostgreSQL (`{ms}ms`)**\n• Users: `{u}`\n• Groups: `{c}`\n• Gacha Cards: `{g}`\n• Marriages: `{m}`",
            reply_markup=back
        )
    elif act == "sys":
        total, used, free = shutil.disk_usage("/")
        await query.message.edit_text(
            f"🖥️ **Server Specs**\n• CPUs: `{os.cpu_count()}`\n• Disk: `{used // (1024**3)}/{total // (1024**3)} GB` (`{free // (1024**3)} GB free`)\n• Python: `{sys.version.split()[0]}`",
            reply_markup=back
        )
    elif act == "cmds":
        await query.bot.set_my_commands([
            BotCommand(command="start", description="Start Ruka"),
            BotCommand(command="help", description="Command Guide"),
            BotCommand(command="ruka", description="Chat with Ruka AI"),
            BotCommand(command="gacha", description="Pull Waifu/Husbando card"),
            BotCommand(command="shop", description="Open Ruka's Shop"),
            BotCommand(command="daily", description="Claim daily coins"),
            BotCommand(command="rank", description="View your Trainer Card"),
            BotCommand(command="settings", description="Group security settings"),
        ])
        await query.answer("✅ Updated Telegram '/' Menu!", show_alert=True)
    elif act == "flush":
        await query.bot.delete_webhook(drop_pending_updates=True)
        await query.answer("🧹 Flushed pending updates!", show_alert=True)
    elif act == "restart":
        await query.answer("🔄 Restarting...", show_alert=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    await query.answer()


# --- 2–7: System & Diagnostics Commands ---
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
    t0 = time.time(); me = await message.bot.get_me(); ms = round((time.time() - t0) * 1000, 2)
    h_mask = f"{CONFIG.API_HASH[:4]}...{CONFIG.API_HASH[-4:]}" if CONFIG.API_HASH else "Missing"
    await message.answer(
        f"🔌 **API Health**\n• API_ID: `{CONFIG.API_ID}`\n• API_HASH: `{h_mask}`\n"
        f"• Bot API: `{ms}ms` (`@{me.username}`)\n• Groq Key: {'✅' if os.getenv('GROQ_API_KEY') else '❌'}"
    )


@router.message(Command("sysinfo", prefix="/!"))
async def sys_info_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    total, used, free = shutil.disk_usage("/")
    await message.answer(f"🖥️ CPUs: `{os.cpu_count()}` | Disk: `{used // (1024**3)}/{total // (1024**3)} GB` | Uptime: `{get_uptime()}`")


@router.message(Command("pipcheck", prefix="/!"))
async def pip_check_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    pkgs = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
    await message.answer("📦 **Packages:**\n```\n" + "\n".join(pkgs[:30]) + "\n```")


@router.message(Command("testdb", prefix="/!"))
async def test_db_cmd(message: Message):
    if not is_dev(message.from_user.id): return
    t0 = time.time(); pool = await get_pool()
    async with pool.acquire() as conn: await conn.fetchval("SELECT 1")
    await message.answer(f"🗄️ **PostgreSQL Ping:** `{round((time.time() - t0) * 1000, 2)}ms` ✅")


@router.message(Command("env", prefix="/!"))
async def env_check_cmd(message: Message):
    if not is_owner(message.from_user.id): return
    keys = ["BOT_TOKEN", "API_ID", "API_HASH", "DB_URL", "GROQ_API_KEY", "LOGS_CHANNEL", "SUPPORT_CHAT_ID"]
    await message.answer("🔐 **Env Status:**\n" + "\n".join(f"• `{k}`: {'✅' if os.getenv(k) else '❌'}" for k in keys))


# --- 8–14: Live Bot Profile & Menu ---
@router.message(Command("setbotcmds", prefix="/!"))
async def set_bot_cmds(message: Message):
    if not is_dev(message.from_user.id): return
    await message.bot.set_my_commands([
        BotCommand(command="start", description="Start Ruka"),
        BotCommand(command="help", description="Command Guide"),
        BotCommand(command="ruka", description="Chat with Ruka AI"),
        BotCommand(command="gacha", description="Pull Waifu/Husbando card"),
        BotCommand(command="shop", description="Open Ruka's Shop"),
        BotCommand(command="daily", description="Claim daily coins"),
        BotCommand(command="rank", description="View your Trainer Card"),
        BotCommand(command="settings", description="Group security settings"),
    ])
    await message.answer("✅ Updated Telegram `/` Command Menu!")


@router.message(Command("clearbotcmds", prefix="/!"))
async def clear_bot_cmds(message: Message):
    if not is_dev(message.from_user.id): return
    await message.bot.delete_my_commands()
    await message.answer("🗑️ Cleared Telegram `/` Command Menu!")


@router.message(Command("setbotname", "setbotdesc", "setbotshort", prefix="/!"))
async def edit_bot_profile(message: Message):
    if not is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer(f"Usage: `/{cmd} <text>`")
    if cmd == "setbotname": await message.bot.set_my_name(p[1][:64])
    elif cmd == "setbotdesc": await message.bot.set_my_description(p[1][:512])
    else: await message.bot.set_my_short_description(p[1][:120])
    await message.answer(f"✅ Updated `{cmd}`!")


@router.message(Command("webhookinfo", "flushupdates", prefix="/!"))
async def webhook_cmds(message: Message):
    if not is_dev(message.from_user.id): return
    if "flush" in message.text.lower():
        await message.bot.delete_webhook(drop_pending_updates=True)
        return await message.answer("🧹 Flushed pending updates!")
    info = await message.bot.get_webhook_info()
    await message.answer(f"🌐 URL: `{info.url or 'Polling'}` | Pending: `{info.pending_update_count}`")


# --- 15–19: Hierarchy ---
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
    lst = CONFIG.SUDO_LIST if "sudo" in cmd else CONFIG.DEV_LIST
    if cmd.startswith("add") and uid not in lst: lst.append(uid); await message.answer(f"✅ Added `{uid}`!")
    elif cmd.startswith("rm") and uid in lst: lst.remove(uid); await message.answer(f"🗑️ Removed `{uid}`!")


# --- 20–26: Economy & DB God Controls ---
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
    await message.answer(f"💎 `{uid}` → Coins: `{s['coins']}` | XP: `{s['xp']}`")


@router.message(Command("giveallcoins", "giveallxp", prefix="/!"))
async def airdrop_all(message: Message):
    if not is_owner(message.from_user.id): return
    p = message.text.split()
    if len(p) < 2 or not p[1].isdigit(): return
    amt, col = int(p[1]), ("coins" if "coins" in message.text.lower() else "xp")
    pool = await get_pool()
    async with pool.acquire() as conn: await conn.execute(f"UPDATE user_stats SET {col} = {col} + $1", amt)
    await message.answer(f"🎉 Airdropped `+{amt} {col}` to ALL users!")


@router.message(Command("toprich", "dbstats", prefix="/!"))
async def db_views(message: Message):
    if not is_sudo(message.from_user.id): return
    pool = await get_pool()
    async with pool.acquire() as conn:
        if "toprich" in message.text.lower():
            rows = await conn.fetch("SELECT user_id, coins FROM user_stats ORDER BY coins DESC LIMIT 10")
            return await message.answer("💰 **Top 10 Richest:**\n" + "\n".join(f"• `{r['user_id']}`: `{r['coins']} 💎`" for r in rows))
        u = await conn.fetchval("SELECT COUNT(*) FROM user_stats")
        c = await conn.fetchval("SELECT COUNT(*) FROM chat_settings")
        g = await conn.fetchval("SELECT COUNT(*) FROM gacha_collection")
        m = await conn.fetchval("SELECT COUNT(*) FROM marriage_data")
    await message.answer(f"🗄️ Users: `{u}` | Groups: `{c}` | Cards: `{g}` | Marriages: `{m}`")


@router.message(Command("resetuser", "wipechat", "sql", prefix="/!"))
async def db_admin_cmds(message: Message):
    if not is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    pool = await get_pool()
    if cmd == "resetuser":
        uid, _ = _uid_amt(message)
        if not uid: return
        async with pool.acquire() as conn: await conn.execute("UPDATE user_stats SET coins=100, xp=0 WHERE user_id=$1", uid)
        return await message.answer(f"🔄 Reset `{uid}`!")
    if cmd == "wipechat":
        p = message.text.split()
        cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
        async with pool.acquire() as conn:
            for tbl in ("chat_settings", "chat_filters", "approved_users", "chat_locks", "chat_blacklists"):
                await conn.execute(f"DELETE FROM {tbl} WHERE chat_id=$1", cid)
        return await message.answer(f"🧹 Wiped `{cid}`!")
    p = message.text.split(None, 1)
    if len(p) < 2: return
    try:
        async with pool.acquire() as conn:
            if p[1].strip().lower().startswith("select"):
                out = "\n".join(str(dict(r)) for r in (await conn.fetch(p[1]))[:20]) or "No rows."
            else:
                out = f"✅ {await conn.execute(p[1])}"
    except Exception as e:
        out = f"❌ {e}"
    await message.answer(f"```\n{out[:3800]}\n```")


# --- 27–33: GBan, Send, Leave, Eval, Shell, Restart ---
@router.message(Command("gban", "ungban", "gbanlist", prefix="/!"))
async def gban_cmds(message: Message):
    if not is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "gbanlist":
        return await message.answer("🌐 **GBanned:** " + ", ".join(map(str, GBANNED_USERS)) if GBANNED_USERS else "None.")
    uid, _ = _uid_amt(message)
    if not uid: return
    if cmd == "gban": GBANNED_USERS.add(uid); await message.answer(f"🌐 **GBanned** `{uid}`!")
    else: GBANNED_USERS.discard(uid); await message.answer(f"🌸 **UnGBanned** `{uid}`!")


@router.message(Command("send", "leavechat", prefix="/!"))
async def remote_cmds(message: Message):
    if not is_owner(message.from_user.id): return
    if "leave" in message.text.lower():
        p = message.text.split()
        cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
        return await message.bot.leave_chat(cid)
    p = message.text.split(None, 2)
    if len(p) >= 3:
        await message.bot.send_message(int(p[1]), p[2]); await message.answer(f"✅ Sent to `{p[1]}`!")


@router.message(Command("eval", "sh", "bash", "restart", prefix="/!"))
async def exec_cmds(message: Message):
    if not is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "restart":
        await message.answer("🔄 **Restarting RuKa-Bot...** 💓")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    p = message.text.split(None, 1)
    if len(p) < 2: return
    if cmd == "eval":
        old = sys.stdout; sys.stdout = out_io = StringIO()
        try:
            exec("async def __a(message):\n" + "\n".join(f"    {l}" for l in p[1].splitlines()), globals(), locals())
            await locals()["__a"](message); out = out_io.getvalue() or "✅ Done."
        except Exception:
            out = traceback.format_exc()
        finally:
            sys.stdout = old
        return await message.answer(f"```python\n{out[:3800]}\n```")
    proc = await asyncio.create_subprocess_shell(p[1], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    so, se = await proc.communicate()
    await message.answer(f"```bash\n{(so.decode() + se.decode()).strip()[:3800] or '✅ Done.'}\n```")
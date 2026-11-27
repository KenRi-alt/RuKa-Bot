import os, sys, time, shutil, asyncio, traceback, importlib.metadata
from io import StringIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA import CONFIG
from RUKA.utils.db import (
    get_pool, get_user_stats, update_user_stats, set_bot_config, get_bot_config,
    set_staff, get_all_staff, set_gban, get_all_gbans, set_botban
)

router = Router()
START_TIME = time.time()


async def is_owner(uid: int) -> bool:
    return uid in (CONFIG.OWNER_LIST or [])


async def is_dev(uid: int) -> bool:
    if await is_owner(uid) or uid in (CONFIG.DEV_LIST or []):
        return True
    return (await get_all_staff()).get(uid) == "dev"


async def is_sudo(uid: int) -> bool:
    if await is_dev(uid) or uid in (CONFIG.SUDO_LIST or []):
        return True
    return (await get_all_staff()).get(uid) in ("dev", "sudo")


def get_uptime() -> str:
    s = int(time.time() - START_TIME)
    d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return f"{d}d {h}h {m}m {s}s"


def _get_ram() -> str:
    try:
        with open("/proc/meminfo") as f:
            lines = {l.split(":")[0]: int(l.split(":")[1].strip().split()[0]) for l in f if ":" in l}
        tot = lines["MemTotal"] // 1024
        avail = lines["MemAvailable"] // 1024
        return f"{tot - avail}MB / {tot}MB"
    except Exception:
        return "N/A"


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


async def _panel_markup() -> InlineKeyboardMarkup:
    m_on = (await get_bot_config("maintenance", "off")) == "on"
    fs = await get_bot_config("forcesub")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 API Health", callback_data="own_api"),
         InlineKeyboardButton(text="🗄️ DB Stats", callback_data="own_db")],
        [InlineKeyboardButton(text="🖥️ Server Specs", callback_data="own_sys"),
         InlineKeyboardButton(text=f"🛠️ Maint: {'ON' if m_on else 'OFF'}", callback_data="own_maint")],
        [InlineKeyboardButton(text=f"📢 ForceSub: {'ON' if fs else 'OFF'}", callback_data="own_fs"),
         InlineKeyboardButton(text="🧹 Clear Cache", callback_data="own_cache")],
        [InlineKeyboardButton(text="📋 Set / Menu", callback_data="own_cmds"),
         InlineKeyboardButton(text="🔄 Restart", callback_data="own_restart")],
        [InlineKeyboardButton(text="❌ Close", callback_data="own_close")],
    ])


# --- 1. Interactive /ownerpanel ---
@router.message(Command("ownerpanel", "devpanel", prefix="/!"))
async def owner_panel_cmd(message: Message):
    if not await is_dev(message.from_user.id):
        return await message.answer("❌ Owner/Dev only!")
    await message.answer(
        f"👑 **Ruka God-Mode Control Center**\n⏱️ Uptime: `{get_uptime()}` | RAM: `{_get_ram()}`",
        reply_markup=await _panel_markup()
    )


@router.callback_query(F.data.startswith("own_"))
async def owner_panel_cb(query: CallbackQuery):
    if not await is_dev(query.from_user.id):
        return await query.answer("❌ Owner/Dev only!", show_alert=True)
    act = query.data.split("_")[1]
    back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back", callback_data="own_back")]])
    if act == "close":
        return await query.message.delete()
    if act == "back":
        return await query.message.edit_text(f"👑 **Ruka God-Mode Control Center**\n⏱️ `{get_uptime()}` | RAM: `{_get_ram()}`", reply_markup=await _panel_markup())
    if act == "maint":
        cur = await get_bot_config("maintenance", "off")
        await set_bot_config("maintenance", "off" if cur == "on" else "on")
        await query.message.edit_reply_markup(reply_markup=await _panel_markup())
        return await query.answer(f"Maintenance -> {'OFF' if cur == 'on' else 'ON'}!")
    if act == "fs":
        fs = await get_bot_config("forcesub")
        return await query.answer(f"ForceSub: {fs or 'OFF'}. Use /forcesub <@channel|off>", show_alert=True)
    if act == "cache":
        from RUKA.plugins.start import PHOTO_CACHE
        from RUKA.plugins.levels_games import RUKA_CACHE
        PHOTO_CACHE.clear()
        return await query.answer("🧹 RAM Image Caches cleared!", show_alert=True)
    if act == "api":
        t0 = time.time(); me = await query.bot.get_me(); ms = round((time.time() - t0) * 1000, 2)
        return await query.message.edit_text(f"🔌 **API Health**\n• Bot: `@{me.username}` (`{ms}ms`)\n• API_ID: `{CONFIG.API_ID}`\n• Groq: {'✅' if os.getenv('GROQ_API_KEY') else '❌'}", reply_markup=back)
    if act == "db":
        t0 = time.time(); pool = await get_pool()
        async with pool.acquire() as conn:
            u = await conn.fetchval("SELECT COUNT(*) FROM user_stats")
            c = await conn.fetchval("SELECT COUNT(*) FROM chat_settings")
            g = await conn.fetchval("SELECT COUNT(*) FROM gacha_collection")
            gb = await conn.fetchval("SELECT COUNT(*) FROM global_bans")
        return await query.message.edit_text(f"🗄️ **DB (`{round((time.time() - t0)*1000, 2)}ms`)**\n• Users: `{u}` | Groups: `{c}`\n• Cards: `{g}` | GBans: `{gb}`", reply_markup=back)
    if act == "sys":
        tot, used, free = shutil.disk_usage("/")
        return await query.message.edit_text(f"🖥️ **Server**\n• RAM: `{_get_ram()}`\n• CPUs: `{os.cpu_count()}`\n• Disk: `{used//(1024**3)}/{tot//(1024**3)} GB`", reply_markup=back)
    if act == "cmds":
        await query.bot.set_my_commands([
            BotCommand(command="start", description="Start Ruka"), BotCommand(command="help", description="Command Guide"),
            BotCommand(command="ruka", description="Chat with Ruka AI"), BotCommand(command="gacha", description="Pull Waifu/Husbando"),
            BotCommand(command="shop", description="Open Shop"), BotCommand(command="daily", description="Claim daily coins"),
            BotCommand(command="rank", description="Trainer Card"), BotCommand(command="settings", description="Group settings"),
        ])
        return await query.answer("✅ Updated `/` Menu!", show_alert=True)
    if act == "restart":
        await query.answer("🔄 Restarting...", show_alert=True)
        os.execv(sys.executable, [sys.executable] + sys.argv)


# --- 2. Broadcast, Announce, ForceSub, Maintenance ---
@router.message(Command("broadcast", prefix="/!"))
async def broadcast_cmd(message: Message):
    if not await is_owner(message.from_user.id): return
    if not message.reply_to_message:
        return await message.answer("Reply to any message with `/broadcast users | groups | all`")
    mode = message.text.split()[1].lower() if len(message.text.split()) > 1 else "all"
    pool = await get_pool()
    targets = []
    async with pool.acquire() as conn:
        if mode in ("users", "all"):
            targets += [r["user_id"] for r in await conn.fetch("SELECT user_id FROM user_stats")]
        if mode in ("groups", "all"):
            targets += [r["chat_id"] for r in await conn.fetch("SELECT chat_id FROM chat_settings")]
    targets = list(set(targets))
    st = await message.answer(f"📢 Broadcasting to `{len(targets)}` targets...")
    ok = fail = 0
    for tid in targets:
        try:
            await message.reply_to_message.copy_to(tid); ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"📢 **Broadcast Done!**\n✅ Sent: `{ok}` | ❌ Failed: `{fail}`")


@router.message(Command("announce", prefix="/!"))
async def announce_cmd(message: Message):
    if not await is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return await message.answer("Usage: `/announce <message>`")
    pool = await get_pool()
    async with pool.acquire() as conn:
        cids = [r["chat_id"] for r in await conn.fetch("SELECT chat_id FROM chat_settings")]
    ok = 0
    for cid in cids:
        try:
            await message.bot.send_message(cid, f"📣 **Official Ruka Announcement**\n\n{p[1]}")
            ok += 1
        except Exception: pass
        await asyncio.sleep(0.05)
    await message.answer(f"📣 Announced to `{ok}/{len(cids)}` groups!")


@router.message(Command("forcesub", prefix="/!"))
async def forcesub_cmd(message: Message):
    if not await is_owner(message.from_user.id): return
    p = message.text.split()
    if len(p) < 2:
        cur = await get_bot_config("forcesub")
        return await message.answer(f"📢 ForceSub: `{cur or 'OFF'}`\nUsage: `/forcesub @channel` or `/forcesub off`")
    val = None if p[1].lower() in ("off", "no", "none") else p[1]
    await set_bot_config("forcesub", val)
    await message.answer(f"📢 ForceSub set to `{val or 'OFF'}`!")


@router.message(Command("maintenance", prefix="/!"))
async def maintenance_cmd(message: Message):
    if not await is_owner(message.from_user.id): return
    p = message.text.split(None, 2)
    if len(p) < 2 or p[1].lower() not in ("on", "off"):
        cur = await get_bot_config("maintenance", "off")
        return await message.answer(f"🛠️ Maintenance: `{cur.upper()}`\nUsage: `/maintenance on [reason]` or `/maintenance off`")
    await set_bot_config("maintenance", p[1].lower())
    if len(p) > 2: await set_bot_config("maintenance_reason", p[2])
    await message.answer(f"🛠️ Maintenance Mode is now **{p[1].upper()}**!")


# --- 3. Diagnostics & System ---
@router.message(Command("stats", "botinfo", "sysinfo", "apihealth", "testdb", "pipcheck", "env", "clearcache", prefix="/!"))
async def diag_cmds(message: Message):
    if not await is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "stats":
        return await message.answer(f"📊 Uptime: `{get_uptime()}` | RAM: `{_get_ram()}` | Py: `{sys.version.split()[0]}`")
    if not await is_dev(message.from_user.id): return
    if cmd == "botinfo":
        me = await message.bot.get_me()
        return await message.answer(f"🤖 `{me.full_name}` (`@{me.username}` | `{me.id}`)\n⏱️ `{get_uptime()}`")
    if cmd == "sysinfo":
        tot, used, free = shutil.disk_usage("/")
        return await message.answer(f"🖥️ RAM: `{_get_ram()}` | CPUs: `{os.cpu_count()}` | Disk: `{used//(1024**3)}/{tot//(1024**3)} GB`")
    if cmd == "apihealth":
        t0 = time.time(); await message.bot.get_me()
        return await message.answer(f"🔌 API: `{round((time.time()-t0)*1000, 2)}ms` | ID: `{CONFIG.API_ID}` | Groq: {'✅' if os.getenv('GROQ_API_KEY') else '❌'}")
    if cmd == "testdb":
        t0 = time.time(); pool = await get_pool()
        async with pool.acquire() as c: await c.fetchval("SELECT 1")
        return await message.answer(f"🗄️ DB Ping: `{round((time.time()-t0)*1000, 2)}ms` ✅")
    if cmd == "pipcheck":
        pkgs = sorted(f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions())
        return await message.answer("```\n" + "\n".join(pkgs[:30]) + "\n```")
    if cmd == "clearcache":
        from RUKA.plugins.start import PHOTO_CACHE
        PHOTO_CACHE.clear(); return await message.answer("🧹 RAM Image Caches cleared!")
    if cmd == "env" and await is_owner(message.from_user.id):
        keys = ["BOT_TOKEN", "API_ID", "API_HASH", "DB_URL", "GROQ_API_KEY", "LOGS_CHANNEL", "SUPPORT_CHAT_ID"]
        await message.answer("🔐 **Env:**\n" + "\n".join(f"• `{k}`: {'✅' if os.getenv(k) else '❌'}" for k in keys))


# --- 4. Remote /send, /chatinfo, /leavechat, Staff & Bot Profile ---
@router.message(Command("send", prefix="/!"))
async def send_as_bot(message: Message):
    if not await is_owner(message.from_user.id): return
    p = message.text.split(None, 2)
    if len(p) < 2 or not p[1].lstrip("-").isdigit():
        return await message.answer("Usage: `/send <chat_id> <text>` (or reply to media with `/send <chat_id>`)")
    cid = int(p[1])
    if message.reply_to_message:
        await message.reply_to_message.copy_to(cid)
    elif len(p) >= 3:
        await message.bot.send_message(cid, p[2])
    else:
        return await message.answer("Provide text or reply to a message!")
    await message.answer(f"✅ Delivered to `{cid}`!")


@router.message(Command("chatinfo", "leavechat", prefix="/!"))
async def chat_ops(message: Message):
    if not await is_dev(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    p = message.text.split()
    cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
    if cmd == "leavechat" and await is_owner(message.from_user.id):
        return await message.bot.leave_chat(cid)
    ch = await message.bot.get_chat(cid)
    cnt = await message.bot.get_chat_member_count(cid)
    await message.answer(f"💬 **{ch.title}** (`{cid}`)\n• Type: `{ch.type}` | Members: `{cnt}`", parse_mode=None)


@router.message(Command("sudolist", "addsudo", "rmsudo", "adddev", "rmdev", prefix="/!"))
async def staff_cmds(message: Message):
    if not await is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "sudolist":
        db_st = await get_all_staff()
        return await message.answer(f"👑 **Owners:** `{CONFIG.OWNER_LIST}`\n🛠️ **Devs:** `{CONFIG.DEV_LIST}`\n⚡ **Sudos:** `{CONFIG.SUDO_LIST}`\n🗄️ **DB Staff:** `{db_st}`")
    if not await is_owner(message.from_user.id): return
    uid, _ = _uid_amt(message)
    if not uid: return await message.answer("Reply or pass User ID!")
    if cmd.startswith("rm"):
        await set_staff(uid, None); await message.answer(f"🗑️ Removed `{uid}` from DB staff!")
    else:
        role = "dev" if "dev" in cmd else "sudo"
        await set_staff(uid, role); await message.answer(f"✅ Promoted `{uid}` to **{role.upper()}** (saved in DB)!")


@router.message(Command("setbotcmds", "clearbotcmds", "setbotname", "setbotdesc", "setbotshort", "webhookinfo", "flushupdates", prefix="/!"))
async def bot_profile_cmds(message: Message):
    if not await is_dev(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "setbotcmds":
        await message.bot.set_my_commands([BotCommand(command="start", description="Start Ruka"), BotCommand(command="help", description="Command Guide"), BotCommand(command="ruka", description="Chat with Ruka AI"), BotCommand(command="gacha", description="Pull card"), BotCommand(command="shop", description="Open Shop"), BotCommand(command="rank", description="Trainer Card")])
        return await message.answer("✅ Updated `/` menu!")
    if cmd == "clearbotcmds": await message.bot.delete_my_commands(); return await message.answer("🗑️ Cleared `/` menu!")
    if cmd == "flushupdates": await message.bot.delete_webhook(drop_pending_updates=True); return await message.answer("🧹 Flushed!")
    if cmd == "webhookinfo":
        i = await message.bot.get_webhook_info(); return await message.answer(f"🌐 URL: `{i.url or 'Polling'}` | Pending: `{i.pending_update_count}`")
    if not await is_owner(message.from_user.id): return
    p = message.text.split(None, 1)
    if len(p) < 2: return
    if cmd == "setbotname": await message.bot.set_my_name(p[1][:64])
    elif cmd == "setbotdesc": await message.bot.set_my_description(p[1][:512])
    else: await message.bot.set_my_short_description(p[1][:120])
    await message.answer(f"✅ Updated `{cmd}`!")


# --- 5. Persistent GBan, BotBan, Economy, SQL, Eval, Shell ---
@router.message(Command("gban", "ungban", "gbanlist", "botban", "botunban", prefix="/!"))
async def global_mod_cmds(message: Message):
    if not await is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "gbanlist":
        rows = await get_all_gbans()
        return await message.answer("🌐 **GBans:**\n" + "\n".join(f"• `{r['user_id']}`: {r['reason']}" for r in rows) if rows else "None.")
    uid, _ = _uid_amt(message)
    if not uid: return
    if cmd == "gban": await set_gban(uid, "Global Ban"); await message.answer(f"🌐 **GBanned** `{uid}` (saved in DB)!")
    elif cmd == "ungban": await set_gban(uid, None); await message.answer(f"🌸 **UnGBanned** `{uid}`!")
    elif cmd == "botban": await set_botban(uid, "Banned"); await message.answer(f"🚫 **Bot-Banned** `{uid}`!")
    elif cmd == "botunban": await set_botban(uid, None); await message.answer(f"✅ **Bot-Unbanned** `{uid}`!")


@router.message(Command("addcoins", "rmcoins", "addxp", "giveallcoins", "giveallxp", "toprich", "resetuser", "dbstats", "wipechat", "sql", prefix="/!"))
async def god_db_econ(message: Message):
    if not await is_sudo(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    pool = await get_pool()
    if cmd == "toprich":
        async with pool.acquire() as c: rows = await c.fetch("SELECT user_id, coins FROM user_stats ORDER BY coins DESC LIMIT 10")
        return await message.answer("💰 **Top 10:**\n" + "\n".join(f"• `{r['user_id']}`: `{r['coins']} 💎`" for r in rows))
    if cmd == "dbstats":
        async with pool.acquire() as c:
            u, ch, g, m = await c.fetchval("SELECT COUNT(*) FROM user_stats"), await c.fetchval("SELECT COUNT(*) FROM chat_settings"), await c.fetchval("SELECT COUNT(*) FROM gacha_collection"), await c.fetchval("SELECT COUNT(*) FROM marriage_data")
        return await message.answer(f"🗄️ Users: `{u}` | Groups: `{ch}` | Cards: `{g}` | Marriages: `{m}`")
    if not await is_owner(message.from_user.id): return
    if cmd in ("addcoins", "rmcoins", "addxp"):
        uid, amt = _uid_amt(message)
        if not uid or amt is None: return
        await update_user_stats(uid, coins=(amt if cmd == "addcoins" else (-abs(amt) if cmd == "rmcoins" else None)), xp=(amt if cmd == "addxp" else None))
        s = await get_user_stats(uid)
        return await message.answer(f"💎 `{uid}` → `{s['coins']} 💎` | `{s['xp']} XP`")
    if cmd in ("giveallcoins", "giveallxp"):
        p = message.text.split()
        if len(p) > 1 and p[1].isdigit():
            col = "coins" if "coins" in cmd else "xp"
            async with pool.acquire() as c: await c.execute(f"UPDATE user_stats SET {col} = {col} + $1", int(p[1]))
            return await message.answer(f"🎉 Airdropped `+{p[1]} {col}` to ALL users!")
    if cmd == "resetuser":
        uid, _ = _uid_amt(message)
        if uid:
            async with pool.acquire() as c: await c.execute("UPDATE user_stats SET coins=100, xp=0 WHERE user_id=$1", uid)
            return await message.answer(f"🔄 Reset `{uid}`!")
    if cmd == "wipechat":
        p = message.text.split()
        cid = int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else message.chat.id
        async with pool.acquire() as c:
            for tbl in ("chat_settings", "chat_filters", "approved_users", "chat_locks", "chat_blacklists"):
                await c.execute(f"DELETE FROM {tbl} WHERE chat_id=$1", cid)
        return await message.answer(f"🧹 Wiped `{cid}`!")
    p = message.text.split(None, 1)
    if len(p) < 2: return
    try:
        async with pool.acquire() as c:
            out = "\n".join(str(dict(r)) for r in (await c.fetch(p[1]))[:20]) if p[1].strip().lower().startswith("select") else f"✅ {await c.execute(p[1])}"
    except Exception as e:
        out = f"❌ {e}"
    await message.answer(f"```\n{out[:3800]}\n```")


@router.message(Command("eval", "sh", "bash", "restart", prefix="/!"))
async def exec_cmds(message: Message):
    if not await is_owner(message.from_user.id): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "restart":
        await message.answer("🔄 **Restarting...** 💓"); os.execv(sys.executable, [sys.executable] + sys.argv)
    p = message.text.split(None, 1)
    if len(p) < 2: return
    if cmd == "eval":
        old = sys.stdout; sys.stdout = out_io = StringIO()
        try:
            exec("async def __a(message):\n" + "\n".join(f"    {l}" for l in p[1].splitlines()), globals(), locals())
            await locals()["__a"](message); out = out_io.getvalue() or "✅ Done."
        except Exception: out = traceback.format_exc()
        finally: sys.stdout = old
        return await message.answer(f"```python\n{out[:3800]}\n```")
    proc = await asyncio.create_subprocess_shell(p[1], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    so, se = await proc.communicate()
    await message.answer(f"```bash\n{(so.decode() + se.decode()).strip()[:3800] or '✅ Done.'}\n```")
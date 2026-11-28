import re, time, uuid
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_profile
from RUKA.utils.db import (
    get_pool, get_chat_settings, set_chat_num, set_lock, get_locks,
    set_blacklist, get_blacklists, update_warn, get_warns, set_rules, get_rules,
    save_note, get_note, get_notes, delete_note, approve_user, unapprove_user,
    is_approved, get_approved, set_log_channel, unset_log_channel, get_log_channel,
    create_fed, join_fed, get_chat_fed, fban_user, funban_user, get_filters
)

router = Router()
USER_CONNECTED, LAST_CONNECTED, AFK_USERS, FLOOD_TRACKER = {}, {}, {}, {}
WARN_MODES, FLOOD_MODES, BL_MODES, REPORTS_OFF = {}, {}, {}, set()
LOCK_TYPES = {
    "all", "links", "url", "invitelink", "botlink", "stickers", "gif",
    "photo", "video", "voice", "document", "forwards", "media", "spoiler",
    "email", "phone", "cjk", "cyrillic"
}


async def _is_adm(m: Message, notify: bool = True) -> bool:
    if m.chat.type not in ("group", "supergroup"): return False
    if m.sender_chat and m.sender_chat.id == m.chat.id: return True
    mem = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
    if mem.status in ("creator", "administrator"): return True
    if notify: await m.answer("❌ You must be an admin to use this command!")
    return False


async def _punish(bot, cid: int, uid: int, mode: str):
    if mode == "ban": await bot.ban_chat_member(cid, uid)
    elif mode == "kick": await bot.ban_chat_member(cid, uid); await bot.unban_chat_member(cid, uid)
    elif mode == "mute": await bot.restrict_chat_member(cid, uid, ChatPermissions(can_send_messages=False))


@router.message(Command("warn", "dwarn", "swarn", "rmwarn", "unwarn", "resetwarn", "resetwarns", "warns", "warnlimit", "setwarnlimit", "warnmode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "warns":
        t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
        w, s = await get_warns(message.chat.id, t.id), await get_chat_settings(message.chat.id)
        return await message.answer(f"⚠️ {t.full_name}: {w}/{s.get('warn_limit', 3)} warns", parse_mode=None)
    if not await _is_adm(message): return
    if cmd in ("warn", "dwarn", "swarn"):
        if not message.reply_to_message: return await message.answer("Reply to a user to warn them!")
        t = message.reply_to_message.from_user
        if cmd == "dwarn":
            try: await message.reply_to_message.delete()
            except Exception: pass
        elif cmd == "swarn":
            try: await message.delete()
            except Exception: pass
        lim = (await get_chat_settings(message.chat.id)).get("warn_limit", 3)
        w, mode = await update_warn(message.chat.id, t.id, delta=1), WARN_MODES.get(message.chat.id, "ban")
        if w >= lim:
            await update_warn(message.chat.id, t.id, reset=True); await _punish(message.bot, message.chat.id, t.id, mode)
            if cmd != "swarn": return await message.answer(f"🔨 {t.full_name} hit {lim}/{lim} warns ({mode})!", parse_mode=None)
            return
        if cmd != "swarn": await message.answer(f"⚠️ Warned {t.full_name} ({w}/{lim})", parse_mode=None)
    elif cmd in ("rmwarn", "unwarn") and message.reply_to_message:
        await message.answer(f"🌸 Removed 1 warn! Current: `{await update_warn(message.chat.id, message.reply_to_message.from_user.id, delta=-1)}`")
    elif cmd in ("resetwarn", "resetwarns") and message.reply_to_message:
        await update_warn(message.chat.id, message.reply_to_message.from_user.id, reset=True); await message.answer("✨ Warnings reset!")
    elif cmd in ("warnlimit", "setwarnlimit") and len(message.text.split()) > 1 and message.text.split()[1].isdigit():
        val = max(1, int(message.text.split()[1])); await set_chat_num(message.chat.id, "warn_limit", val); await message.answer(f"⚙️ Warn limit: **{val}**")
    elif cmd == "warnmode" and len(message.text.split()) > 1 and message.text.split()[1].lower() in ("ban", "mute", "kick"):
        WARN_MODES[message.chat.id] = message.text.split()[1].lower(); await message.answer(f"⚙️ Warn mode: **{WARN_MODES[message.chat.id]}**")


@router.message(Command("setflood", "antiflood", "floodmode", "flood", "addblocklist", "blacklist", "rmblocklist", "unblacklist", "blocklist", "blacklists", "blocklistmode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def flood_bl_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower(); p = message.text.split(None, 1)
    if cmd == "flood":
        s = await get_chat_settings(message.chat.id)
        return await message.answer(f"🌊 Antiflood: `{s.get('flood_limit', 0)} msgs/4s` | Mode: `{FLOOD_MODES.get(message.chat.id, 'mute')}`")
    if cmd in ("blocklist", "blacklists"):
        words = await get_blacklists(message.chat.id)
        return await message.answer("🚫 **Blocklist:**\n• " + "\n• ".join(words) if words else "Blocklist is empty.")
    if not await _is_adm(message): return
    if cmd in ("setflood", "antiflood"):
        arg = p[1].lower() if len(p) > 1 else "0"
        val = 0 if arg in ("off", "no", "0") else (int(arg) if arg.isdigit() else 0)
        await set_chat_num(message.chat.id, "flood_limit", val); await message.answer(f"🌊 Antiflood: **{val} msgs/4s**" if val > 0 else "🌊 Antiflood disabled.")
    elif cmd == "floodmode" and len(p) > 1 and p[1].lower() in ("ban", "mute", "kick"):
        FLOOD_MODES[message.chat.id] = p[1].lower(); await message.answer(f"🌊 Flood mode: **{p[1].lower()}**")
    elif cmd in ("addblocklist", "blacklist") and len(p) > 1:
        await set_blacklist(message.chat.id, p[1].lower(), True); await message.answer(f"🚫 Added `{p[1].lower()}`!")
    elif cmd in ("rmblocklist", "unblacklist") and len(p) > 1:
        await set_blacklist(message.chat.id, p[1].lower(), False); await message.answer(f"✅ Removed `{p[1].lower()}`!")
    elif cmd == "blocklistmode" and len(p) > 1 and p[1].lower() in ("del", "ban", "mute", "kick"):
        BL_MODES[message.chat.id] = p[1].lower(); await message.answer(f"🚫 Blocklist mode: **{p[1].lower()}**")


@router.message(Command("lock", "unlock", "locks", "locktypes", "nightmode", prefix="/!"))
async def lock_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "locktypes": return await message.answer("🔒 **Types:** `" + "`, `".join(sorted(LOCK_TYPES)) + "`")
    if message.chat.type not in ("group", "supergroup"): return await message.answer("❌ Groups only!")
    if cmd == "locks":
        ls = await get_locks(message.chat.id)
        return await message.answer("🔒 **Locks:** " + ", ".join(sorted(ls)) if ls else "🔓 No locks active.")
    if not await _is_adm(message): return
    if cmd == "nightmode":
        mode = message.text.split()[1].lower() if len(message.text.split()) > 1 else "on"
        for lt in ("media", "stickers", "gif", "links"): await set_lock(message.chat.id, lt, mode == "on")
        return await message.answer("🌙 **Night Mode ON!**" if mode == "on" else "☀️ **Night Mode OFF!**")
    p = message.text.split()
    if len(p) < 2 or p[1].lower() not in LOCK_TYPES: return await message.answer("Usage: `/lock <type>` (see `/locktypes`)")
    un = cmd == "unlock"
    await set_lock(message.chat.id, p[1].lower(), not un)
    await message.answer(f"{'🔓 Unlocked' if un else '🔒 Locked'} **{p[1].lower()}**!")


@router.message(Command("approve", "unapprove", "approval", "approved", "unapproveall", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def approval_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "approval":
        t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
        return await message.answer(f"🛡️ {t.full_name}: {'✅ Approved' if await is_approved(message.chat.id, t.id) else '❌ Not Approved'}", parse_mode=None)
    if cmd == "approved":
        uids = await get_approved(message.chat.id)
        return await message.answer("✅ **Approved:**\n" + "\n".join(f"• `{u}`" for u in uids) if uids else "None.")
    if not await _is_adm(message): return
    if cmd == "approve" and message.reply_to_message: await approve_user(message.chat.id, message.reply_to_message.from_user.id); await message.answer("✅ Approved!")
    elif cmd == "unapprove" and message.reply_to_message: await unapprove_user(message.chat.id, message.reply_to_message.from_user.id); await message.answer("❌ Unapproved.")
    elif cmd == "unapproveall":
        pool = await get_pool()
        async with pool.acquire() as conn: await conn.execute("DELETE FROM approved_users WHERE chat_id=$1", message.chat.id)
        await message.answer("🧹 Unapproved all users.")


@router.message(Command("report", "reports", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
@router.message(F.text.lower().contains("@admin"), F.chat.type.in_({"group", "supergroup"}))
async def report_cmds(message: Message):
    if message.text.lower().startswith(("/reports", "!reports")):
        if not await _is_adm(message): return
        off = len(message.text.split()) > 1 and message.text.split()[1].lower() in ("off", "no")
        (REPORTS_OFF.add if off else REPORTS_OFF.discard)(message.chat.id)
        return await message.answer("🔕 Reports OFF." if off else "🔔 Reports ON.")
    if message.chat.id in REPORTS_OFF or not message.reply_to_message or await _is_adm(message, notify=False): return
    t = message.reply_to_message.from_user
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔨 Ban", callback_data=f"rep_ban_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🔇 Mute", callback_data=f"rep_mute_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🗑️ Del", callback_data=f"rep_del_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="✅ Dismiss", callback_data="rep_dismiss_0_0"),
    ]])
    await message.answer(f"🚨 Reported {t.full_name} ({t.id})!", reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("rep_"))
async def report_cb(query: CallbackQuery):
    m = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
    if m.status not in ("creator", "administrator"): return await query.answer("❌ Admins only!", show_alert=True)
    _, act, uid, mid = query.data.split("_"); cid, uid, mid = query.message.chat.id, int(uid), int(mid)
    if act == "ban": await query.bot.ban_chat_member(cid, uid); await query.message.edit_text(f"🔨 Banned {uid}")
    elif act == "mute": await query.bot.restrict_chat_member(cid, uid, ChatPermissions(can_send_messages=False)); await query.message.edit_text(f"🔇 Muted {uid}")
    elif act == "del": await query.bot.delete_message(cid, mid); await query.message.edit_text("🗑️ Deleted!")
    else: await query.message.edit_text("✅ Dismissed.")
    await query.answer()


@router.message(Command("setlog", "unsetlog", "logchannel", "newfed", "joinfed", "leavefed", "fban", "funban", prefix="/!"))
async def log_fed_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower(); p = message.text.split(None, 1)
    if cmd == "newfed" and len(p) > 1:
        fid = str(uuid.uuid4())[:8]; await create_fed(fid, p[1], message.from_user.id)
        return await message.answer(f"🌐 **Fed ID:** `{fid}`")
    if message.chat.type not in ("group", "supergroup"): return
    if cmd == "logchannel":
        lid = await get_log_channel(message.chat.id); return await message.answer(f"📜 Log Channel: `{lid}`" if lid else "None.")
    if not await _is_adm(message): return
    if cmd == "setlog" and len(p) > 1 and p[1].lstrip("-").isdigit(): await set_log_channel(message.chat.id, int(p[1])); await message.answer(f"📜 Log set to `{p[1]}`!")
    elif cmd == "unsetlog": await unset_log_channel(message.chat.id); await message.answer("📜 Log unset.")
    elif cmd == "joinfed" and len(p) > 1: await join_fed(message.chat.id, p[1]); await message.answer(f"🌐 Joined Fed `{p[1]}`!")
    elif cmd == "leavefed":
        pool = await get_pool()
        async with pool.acquire() as conn: await conn.execute("DELETE FROM fed_chats WHERE chat_id=$1", message.chat.id)
        await message.answer("🌐 Left fed.")
    elif cmd in ("fban", "funban"):
        fid = await get_chat_fed(message.chat.id)
        if not fid: return await message.answer("❌ Not in a fed!")
        if cmd == "fban" and message.reply_to_message:
            t = message.reply_to_message.from_user
            await fban_user(fid, t.id, p[1] if len(p) > 1 else "Fed Banned"); await message.bot.ban_chat_member(message.chat.id, t.id)
            await message.answer(f"🌐 Fed-Banned {t.full_name}!", parse_mode=None)
        elif cmd == "funban" and len(p) > 1 and p[1].isdigit(): await funban_user(fid, int(p[1])); await message.answer(f"🌸 Fed-Unbanned `{p[1]}`!")


@router.message(Command("setrules", "rules", "resetrules", "save", "get", "notes", "clear", "connect", "disconnect", "reconnect", "connection", "privacy", "info", "id", "ping", "afk", "kickme", "groupstats", prefix="/!"))
async def util_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "privacy": return await message.answer("🔒 Ruka stores only ID, XP, Coins, Marriage/Family & Gacha cards. Contact @Nocis_creed for removal.")
    if cmd == "id": return await message.answer(f"💬 Chat: `{message.chat.id}`\n👤 You: `{message.from_user.id}`")
    if cmd == "ping": s = time.time(); m = await message.answer("🏓 Pinging..."); return await m.edit_text(f"💓 **Pong!** `{round((time.time() - s) * 1000, 2)}ms`")
    if cmd == "afk":
        rsn = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else "Busy!"
        AFK_USERS[message.from_user.id] = (time.time(), rsn); return await message.answer(f"💤 {message.from_user.full_name} is AFK: {rsn}", parse_mode=None)
    if cmd == "kickme" and message.chat.type in ("group", "supergroup"):
        try: await message.bot.ban_chat_member(message.chat.id, message.from_user.id); await message.bot.unban_chat_member(message.chat.id, message.from_user.id); return await message.answer("👋 Bye!")
        except Exception: return await message.answer("❌ I can't kick you!")
    if cmd == "groupstats" and message.chat.type in ("group", "supergroup"):
        return await message.answer(f"📊 {message.chat.title}\n• Members: {await message.bot.get_chat_member_count(message.chat.id)}\n• Locks: {len(await get_locks(message.chat.id))}", parse_mode=None)
    if cmd == "info":
        t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
        pfp = None
        try:
            ph = await message.bot.get_user_profile_photos(t.id, limit=1)
            if ph.total_count > 0: f = await message.bot.get_file(ph.photos[0][-1].file_id); pfp = BytesIO(); await message.bot.download_file(f.file_path, pfp); pfp.seek(0)
        except Exception: pass
        img = generate_4k_profile(t.first_name, t.id, rank="Member", xp=50, pfp_bytes=pfp)
        return await message.answer_photo(BufferedInputFile(img.getvalue(), filename="info.jpg"), caption=f"👤 {t.full_name}\nID: {t.id} | @{t.username or 'None'}", parse_mode=None)
    if cmd in ("connect", "disconnect", "reconnect", "connection"):
        uid = message.from_user.id
        if cmd == "disconnect":
            if uid in USER_CONNECTED: LAST_CONNECTED[uid] = USER_CONNECTED.pop(uid)
            return await message.answer("🔌 Disconnected.")
        if cmd == "reconnect" and uid in LAST_CONNECTED: USER_CONNECTED[uid] = LAST_CONNECTED[uid]; return await message.answer(f"🔗 Reconnected to `{USER_CONNECTED[uid]}`!")
        if cmd == "connection": return await message.answer(f"🔗 Connected: `{USER_CONNECTED.get(uid)}`")
        if message.chat.type != "private": USER_CONNECTED[uid] = message.chat.id; return await message.answer("🔗 Connected!")
        p = message.text.split()
        if len(p) > 1 and p[1].lstrip("-").isdigit(): USER_CONNECTED[uid] = int(p[1]); return await message.answer(f"🔗 Connected to `{p[1]}`!")
    if message.chat.type not in ("group", "supergroup"): return
    if cmd == "rules": r = await get_rules(message.chat.id); return await message.answer(f"📜 **Rules:**\n\n{r}" if r else "No rules set!")
    if cmd == "notes": ns = await get_notes(message.chat.id); return await message.answer("📝 **Notes:** " + ", ".join(ns) if ns else "No notes.")
    if cmd == "get" and len(message.text.split()) > 1: return await message.answer(await get_note(message.chat.id, message.text.split()[1]) or "❌ Not found.", parse_mode=None)
    if not await _is_adm(message): return
    if cmd == "setrules" and len(message.text.split()) > 1: await set_rules(message.chat.id, message.text.split(None, 1)[1]); await message.answer("📜 Rules saved!")
    elif cmd == "resetrules": await set_rules(message.chat.id, ""); await message.answer("📜 Rules reset.")
    elif cmd == "save" and len(message.text.split()) >= 3: p = message.text.split(None, 2); await save_note(message.chat.id, p[1], p[2]); await message.answer(f"📝 Saved `{p[1].lower()}`!")
    elif cmd == "clear" and len(message.text.split()) > 1: await delete_note(message.chat.id, message.text.split()[1]); await message.answer("🗑️ Deleted!")


@router.message(F.chat.type.in_({"group", "supergroup"}), ~F.text.startswith(("/", "!")))
async def security_watcher(message: Message):
    if not message.from_user or message.from_user.is_bot: raise SkipHandler()
    cid, uid, txt = message.chat.id, message.from_user.id, (message.text or message.caption or "")
    if uid in AFK_USERS:
        AFK_USERS.pop(uid, None); await message.answer(f"🌸 Welcome back, {message.from_user.full_name}!", parse_mode=None)
    elif message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id in AFK_USERS:
        await message.answer(f"💤 {message.reply_to_message.from_user.first_name} is AFK: {AFK_USERS[message.reply_to_message.from_user.id][1]}", parse_mode=None)
    if txt:
        for kw, rep in (await get_filters(cid)).items():
            if kw in txt.lower(): await message.reply(rep, parse_mode=None); break
    if await _is_adm(message, notify=False) or await is_approved(cid, uid): raise SkipHandler()
    fl = (await get_chat_settings(cid)).get("flood_limit", 0)
    if fl > 0:
        now = time.time(); ts = [t for t in FLOOD_TRACKER.get((cid, uid), []) if now - t < 4] + [now]; FLOOD_TRACKER[(cid, uid)] = ts
        if len(ts) > fl:
            FLOOD_TRACKER[(cid, uid)] = []; await _punish(message.bot, cid, uid, FLOOD_MODES.get(cid, "mute"))
            return await message.answer(f"🌊 {message.from_user.full_name} punished for flooding!", parse_mode=None)
    if txt:
        low = txt.lower()
        for w in await get_blacklists(cid):
            if re.search(re.escape(w).replace(r"\*", ".*"), low):
                try: await message.delete()
                except Exception: pass
                await _punish(message.bot, cid, uid, BL_MODES.get(cid, "del")); return
    locks = await get_locks(cid)
    if locks and (
        "all" in locks or ("stickers" in locks and message.sticker) or ("gif" in locks and message.animation)
        or ("photo" in locks and message.photo) or ("video" in locks and message.video)
        or ("voice" in locks and message.voice) or ("document" in locks and message.document)
        or ("forwards" in locks and (message.forward_date or message.forward_origin))
        or ("media" in locks and (message.photo or message.video or message.animation or message.document))
        or (("links" in locks or "url" in locks) and ("http://" in txt or "https://" in txt or "t.me/" in txt))
        or ("invitelink" in locks and ("t.me/+" in txt or "joinchat" in txt))
        or ("botlink" in locks and "bot" in txt.lower() and "@" in txt)
        or ("email" in locks and re.search(r"\S+@\S+\.\S+", txt))
        or ("phone" in locks and re.search(r"\+?\d[\d\s\-]{7,}\d", txt))
        or ("spoiler" in locks and "||" in txt)
        or ("cjk" in locks and re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", txt))
        or ("cyrillic" in locks and re.search(r"[\u0400-\u04FF]", txt))
    ):
        try: await message.delete()
        except Exception: pass
        return
    raise SkipHandler()
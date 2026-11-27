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
LOCK_TYPES = {"all", "links", "url", "invitelink", "stickers", "gif", "photo", "video", "voice", "document", "forwards", "media", "cjk", "cyrillic", "emoji"}


async def _is_adm(m: Message) -> bool:
    if m.chat.type not in ("group", "supergroup"):
        return False
    mem = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
    return mem.status in ("creator", "administrator")


async def _log(bot, cid: int, txt: str):
    lid = await get_log_channel(cid)
    if lid:
        try:
            await bot.send_message(lid, txt, parse_mode=None)
        except Exception:
            pass


async def _punish(bot, cid: int, uid: int, mode: str):
    if mode == "ban":
        await bot.ban_chat_member(cid, uid)
    elif mode == "kick":
        await bot.ban_chat_member(cid, uid)
        await bot.unban_chat_member(cid, uid)
    elif mode == "mute":
        await bot.restrict_chat_member(cid, uid, ChatPermissions(can_send_messages=False))


# --- 1. Warnings ---
@router.message(Command("warn", "dwarn", "swarn", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cmd(m: Message):
    if not await _is_adm(m) or not m.reply_to_message:
        return
    cmd = m.text.split()[0].lstrip("/!").lower()
    t = m.reply_to_message.from_user
    if cmd == "dwarn":
        try: await m.reply_to_message.delete()
        except Exception: pass
    elif cmd == "swarn":
        try: await m.delete()
        except Exception: pass
    s = await get_chat_settings(m.chat.id)
    lim = s.get("warn_limit", 3)
    w = await update_warn(m.chat.id, t.id, delta=1)
    mode = WARN_MODES.get(m.chat.id, "ban")
    rsn = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else "No reason"
    if w >= lim:
        await update_warn(m.chat.id, t.id, reset=True)
        await _punish(m.bot, m.chat.id, t.id, mode)
        await _log(m.bot, m.chat.id, f"🔨 {t.full_name} hit {lim}/{lim} warns -> {mode}")
        if cmd != "swarn":
            return await m.answer(f"🔨 {t.full_name} reached {lim}/{lim} warns ({mode})!\nReason: {rsn}", parse_mode=None)
        return
    await _log(m.bot, m.chat.id, f"⚠️ Warned {t.full_name} ({w}/{lim}): {rsn}")
    if cmd != "swarn":
        await m.answer(f"⚠️ Warned {t.full_name} ({w}/{lim})\nReason: {rsn}", parse_mode=None)


@router.message(Command("rmwarn", "unwarn", "resetwarn", "resetwarns", "warns", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def warn_manage(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "warns":
        t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        w, s = await get_warns(m.chat.id, t.id), await get_chat_settings(m.chat.id)
        return await m.answer(f"⚠️ {t.full_name}: {w}/{s.get('warn_limit', 3)} warns", parse_mode=None)
    if not await _is_adm(m) or not m.reply_to_message:
        return
    if cmd in ("rmwarn", "unwarn"):
        w = await update_warn(m.chat.id, m.reply_to_message.from_user.id, delta=-1)
        await m.answer(f"🌸 Removed 1 warn! Current: `{w}`")
    else:
        await update_warn(m.chat.id, m.reply_to_message.from_user.id, reset=True)
        await m.answer("✨ Warnings reset to 0!")


@router.message(Command("warnlimit", "setwarnlimit", "warnmode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cfg(m: Message):
    if not await _is_adm(m): return
    p = m.text.split()
    if "mode" in p[0].lower():
        if len(p) > 1 and p[1].lower() in ("ban", "mute", "kick"):
            WARN_MODES[m.chat.id] = p[1].lower()
            return await m.answer(f"⚙️ Warn mode: **{p[1].lower()}**")
        return await m.answer("Usage: `/warnmode ban | mute | kick`")
    if len(p) > 1 and p[1].isdigit():
        await set_chat_num(m.chat.id, "warn_limit", max(1, int(p[1])))
        await m.answer(f"⚙️ Warn limit: **{max(1, int(p[1]))}**")


# --- 2. Antiflood & Blocklists ---
@router.message(Command("setflood", "antiflood", "floodmode", "flood", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def flood_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "flood":
        s = await get_chat_settings(m.chat.id)
        return await m.answer(f"🌊 Antiflood: `{s.get('flood_limit', 0)} msgs/4s` | Mode: `{FLOOD_MODES.get(m.chat.id, 'mute')}`")
    if not await _is_adm(m): return
    p = m.text.split()
    if cmd == "floodmode" and len(p) > 1 and p[1].lower() in ("ban", "mute", "kick"):
        FLOOD_MODES[m.chat.id] = p[1].lower()
        return await m.answer(f"🌊 Flood mode: **{p[1].lower()}**")
    val = 0 if len(p) < 2 or p[1].lower() in ("off", "no", "0") else (int(p[1]) if p[1].isdigit() else 0)
    await set_chat_num(m.chat.id, "flood_limit", val)
    await m.answer(f"🌊 Antiflood: **{val} msgs/4s**" if val > 0 else "🌊 Antiflood disabled.")


@router.message(Command("addblocklist", "blacklist", "rmblocklist", "unblacklist", "blocklist", "blacklists", "blocklistmode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def bl_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd in ("blocklist", "blacklists"):
        ws = await get_blacklists(m.chat.id)
        return await m.answer("🚫 **Blocklist:**\n• " + "\n• ".join(ws) if ws else "Blocklist is empty.")
    if not await _is_adm(m): return
    p = m.text.split(None, 1)
    if cmd == "blocklistmode" and len(p) > 1 and p[1].lower() in ("del", "ban", "mute", "kick"):
        BL_MODES[m.chat.id] = p[1].lower()
        return await m.answer(f"🚫 Blocklist mode: **{p[1].lower()}**")
    if len(p) < 2: return
    w = p[1].lower()
    is_rm = cmd.startswith(("rm", "un"))
    await set_blacklist(m.chat.id, w, not is_rm)
    await m.answer(f"{'✅ Removed' if is_rm else '🚫 Added'} `{w}`")


# --- 3. Locks ---
@router.message(Command("lock", "unlock", "locks", "locktypes", "nightmode", prefix="/!"))
async def lock_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "locktypes":
        return await m.answer("🔒 **Types:** `" + "`, `".join(sorted(LOCK_TYPES)) + "`")
    if m.chat.type not in ("group", "supergroup"): return
    if cmd == "locks":
        ls = await get_locks(m.chat.id)
        return await m.answer("🔒 **Active:** " + ", ".join(sorted(ls)) if ls else "🔓 No locks active.")
    if not await _is_adm(m): return
    p = m.text.split()
    if cmd == "nightmode":
        on = (len(p) < 2 or p[1].lower() == "on")
        for lt in ("media", "stickers", "gif", "links"): await set_lock(m.chat.id, lt, on)
        return await m.answer("🌙 **Night Mode ON!**" if on else "☀️ **Night Mode OFF!**")
    if len(p) < 2 or p[1].lower() not in LOCK_TYPES:
        return await m.answer("Usage: `/lock <type>` (see `/locktypes`)")
    lt, un = p[1].lower(), cmd.startswith("un")
    await set_lock(m.chat.id, lt, not un)
    await m.answer(f"{'🔓 Unlocked' if un else '🔒 Locked'} **{lt}**!")


# --- 4. Approval, Reports, Logs, Feds ---
@router.message(Command("approve", "unapprove", "approval", "approved", "unapproveall", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def approval_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "approval":
        t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        return await m.answer(f"🛡️ {t.full_name}: {'✅ Approved' if await is_approved(m.chat.id, t.id) else '❌ Not Approved'}", parse_mode=None)
    if cmd == "approved":
        u = await get_approved(m.chat.id)
        return await m.answer("✅ **Approved:** " + ", ".join(map(str, u)) if u else "No approved users.")
    if cmd == "unapproveall":
        mem = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
        if mem.status != "creator": return await m.answer("❌ Creator only!")
        pool = await get_pool()
        async with pool.acquire() as conn: await conn.execute("DELETE FROM approved_users WHERE chat_id=$1", m.chat.id)
        return await m.answer("🧹 Unapproved all users.")
    if not await _is_adm(m) or not m.reply_to_message: return
    t = m.reply_to_message.from_user
    if cmd == "approve":
        await approve_user(m.chat.id, t.id); await m.answer(f"✅ Approved {t.full_name}!", parse_mode=None)
    else:
        await unapprove_user(m.chat.id, t.id); await m.answer(f"❌ Unapproved {t.full_name}.", parse_mode=None)


@router.message(Command("reports", "report", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
@router.message(F.text.lower().contains("@admin"), F.chat.type.in_({"group", "supergroup"}))
async def report_cmds(m: Message):
    if m.text and m.text.lstrip("/!").lower().startswith("reports"):
        if not await _is_adm(m): return
        off = len(m.text.split()) > 1 and m.text.split()[1].lower() in ("off", "no")
        (REPORTS_OFF.add if off else REPORTS_OFF.discard)(m.chat.id)
        return await m.answer("🔕 Reports disabled." if off else "🔔 Reports enabled.")
    if m.chat.id in REPORTS_OFF or not m.reply_to_message or await _is_adm(m): return
    t = m.reply_to_message.from_user
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔨 Ban", callback_data=f"rep_ban_{t.id}_{m.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🔇 Mute", callback_data=f"rep_mute_{t.id}_{m.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🗑️ Del", callback_data=f"rep_del_{t.id}_{m.reply_to_message.message_id}"),
        InlineKeyboardButton(text="✅ Dismiss", callback_data="rep_dismiss_0_0"),
    ]])
    await m.answer(f"🚨 Reported {t.full_name} ({t.id})!", reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("rep_"))
async def report_cb(q: CallbackQuery):
    mem = await q.bot.get_chat_member(q.message.chat.id, q.from_user.id)
    if mem.status not in ("creator", "administrator"): return await q.answer("❌ Admins only!", show_alert=True)
    _, act, uid, mid = q.data.split("_"); cid, uid, mid = q.message.chat.id, int(uid), int(mid)
    if act == "ban": await q.bot.ban_chat_member(cid, uid); await q.message.edit_text(f"🔨 Banned {uid}", parse_mode=None)
    elif act == "mute": await q.bot.restrict_chat_member(cid, uid, ChatPermissions(can_send_messages=False)); await q.message.edit_text(f"🔇 Muted {uid}", parse_mode=None)
    elif act == "del": await q.bot.delete_message(cid, mid); await q.message.edit_text("🗑️ Deleted.", parse_mode=None)
    else: await q.message.edit_text("✅ Dismissed.")
    await q.answer()


@router.message(Command("setlog", "unsetlog", "logchannel", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def log_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "logchannel":
        lid = await get_log_channel(m.chat.id)
        return await m.answer(f"📜 Log Channel: `{lid}`" if lid else "No log channel set.")
    if not await _is_adm(m): return
    if cmd == "unsetlog": await unset_log_channel(m.chat.id); return await m.answer("📜 Log channel unset.")
    p = m.text.split()
    if len(p) > 1 and p[1].lstrip("-").isdigit():
        await set_log_channel(m.chat.id, int(p[1])); await m.answer(f"📜 Log channel: `{p[1]}`")


@router.message(Command("newfed", "joinfed", "leavefed", "fban", "funban", prefix="/!"))
async def fed_cmds(m: Message):
    cmd, p = m.text.split()[0].lstrip("/!").lower(), m.text.split(None, 1)
    if cmd == "newfed" and len(p) > 1:
        fid = str(uuid.uuid4())[:8]; await create_fed(fid, p[1], m.from_user.id)
        return await m.answer(f"🌐 **Fed Created!** ID: `{fid}`")
    if m.chat.type not in ("group", "supergroup") or not await _is_adm(m): return
    if cmd == "joinfed" and len(p) > 1:
        await join_fed(m.chat.id, p[1]); return await m.answer(f"🌐 Joined Fed `{p[1]}`")
    if cmd == "leavefed":
        pool = await get_pool()
        async with pool.acquire() as conn: await conn.execute("DELETE FROM fed_chats WHERE chat_id=$1", m.chat.id)
        return await m.answer("🌐 Left federation.")
    fid = await get_chat_fed(m.chat.id)
    if not fid: return await m.answer("❌ Not in a federation!")
    if cmd == "fban" and m.reply_to_message:
        t = m.reply_to_message.from_user
        await fban_user(fid, t.id, p[1] if len(p) > 1 else "Fed Banned")
        await m.bot.ban_chat_member(m.chat.id, t.id)
        await m.answer(f"🌐 Fed-Banned {t.full_name}!", parse_mode=None)
    elif cmd == "funban" and len(p) > 1 and p[1].isdigit():
        await funban_user(fid, int(p[1])); await m.answer(f"🌸 Fed-Unbanned `{p[1]}`")


# --- 5. Rules, Notes, Connect, Privacy, Info, Misc ---
@router.message(Command("setrules", "rules", "resetrules", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def rules_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "rules":
        r = await get_rules(m.chat.id)
        return await m.answer(f"📜 **Rules:**\n\n{r}" if r else "📜 No rules set!")
    if not await _is_adm(m): return
    if cmd == "resetrules": await set_rules(m.chat.id, ""); return await m.answer("📜 Rules reset.")
    if len(m.text.split()) > 1: await set_rules(m.chat.id, m.text.split(None, 1)[1]); await m.answer("📜 Rules saved!")


@router.message(Command("save", "get", "notes", "clear", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def notes_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "notes":
        ns = await get_notes(m.chat.id); return await m.answer("📝 **Notes:** " + ", ".join(ns) if ns else "No notes.")
    if cmd == "get" and len(m.text.split()) > 1:
        n = await get_note(m.chat.id, m.text.split()[1]); return await m.answer(n if n else "❌ Not found.", parse_mode=None)
    if not await _is_adm(m): return
    if cmd == "save" and len(m.text.split()) >= 3:
        p = m.text.split(None, 2); await save_note(m.chat.id, p[1], p[2]); await m.answer(f"📝 Saved `{p[1].lower()}`!")
    elif cmd == "clear" and len(m.text.split()) > 1:
        await delete_note(m.chat.id, m.text.split()[1]); await m.answer("🗑️ Deleted!")


@router.message(Command("connect", "disconnect", "reconnect", "connection", prefix="/!"))
async def connect_cmds(m: Message):
    cmd, uid = m.text.split()[0].lstrip("/!").lower(), m.from_user.id
    if cmd == "disconnect":
        if uid in USER_CONNECTED: LAST_CONNECTED[uid] = USER_CONNECTED.pop(uid)
        return await m.answer("🔌 Disconnected.")
    if cmd == "reconnect" and uid in LAST_CONNECTED:
        USER_CONNECTED[uid] = LAST_CONNECTED[uid]; return await m.answer(f"🔗 Reconnected to `{USER_CONNECTED[uid]}`!")
    if cmd == "connection":
        return await m.answer(f"🔗 Connected: `{USER_CONNECTED.get(uid)}`" if uid in USER_CONNECTED else "❌ Not connected.")
    if m.chat.type != "private": USER_CONNECTED[uid] = m.chat.id; return await m.answer(f"🔗 Connected to **{m.chat.title}**!")
    p = m.text.split()
    if len(p) > 1 and p[1].lstrip("-").isdigit(): USER_CONNECTED[uid] = int(p[1]); await m.answer(f"🔗 Connected to `{p[1]}`!")


@router.message(Command("privacy", "info", "id", "ping", "afk", prefix="/!"))
async def util_cmds(m: Message):
    cmd = m.text.split()[0].lstrip("/!").lower()
    if cmd == "privacy":
        return await m.answer("🔒 **Privacy:** Ruka stores only your ID, XP, Coins, Marriage/Family & Gacha cards. Contact @Nocis_creed for removal.")
    if cmd == "id":
        return await m.answer(f"💬 Chat: `{m.chat.id}`\n👤 You: `{m.from_user.id}`")
    if cmd == "ping":
        s = time.time(); msg = await m.answer("🏓 Pinging...")
        return await msg.edit_text(f"💓 **Pong!** `{round((time.time() - s) * 1000, 2)}ms`")
    if cmd == "afk":
        rsn = m.text.split(None, 1)[1] if len(m.text.split()) > 1 else "Busy!"
        AFK_USERS[m.from_user.id] = (time.time(), rsn)
        return await m.answer(f"💤 {m.from_user.full_name} is **AFK**: {rsn}", parse_mode=None)
    t = m.reply_to_message.from_user if m.reply_to_message else m.from_user
    await m.bot.send_chat_action(m.chat.id, "upload_photo")
    pfp = None
    try:
        ph = await m.bot.get_user_profile_photos(t.id, limit=1)
        if ph.total_count > 0:
            f = await m.bot.get_file(ph.photos[0][-1].file_id)
            pfp = BytesIO(); await m.bot.download_file(f.file_path, pfp); pfp.seek(0)
    except Exception: pass
    img = generate_4k_profile(t.first_name, t.id, rank="Member", xp=50, pfp_bytes=pfp)
    await m.answer_photo(BufferedInputFile(img.getvalue(), filename="info.jpg"),
                         caption=f"👤 User Info\n• Name: {t.full_name}\n• ID: {t.id}\n• Username: @{t.username or 'None'}", parse_mode=None)


# --- 6. Live Security, Filter & AFK Watcher (Passes clean messages down via SkipHandler) ---
@router.message(F.chat.type.in_({"group", "supergroup"}), ~F.text.startswith(("/", "!")))
async def security_watcher(m: Message):
    if not m.from_user or m.from_user.is_bot:
        raise SkipHandler()
    cid, uid = m.chat.id, m.from_user.id
    txt = m.text or m.caption or ""

    if uid in AFK_USERS:
        AFK_USERS.pop(uid, None); await m.answer(f"🌸 Welcome back, {m.from_user.full_name}!", parse_mode=None)
    elif m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.id in AFK_USERS:
        await m.answer(f"💤 {m.reply_to_message.from_user.first_name} is AFK: {AFK_USERS[m.reply_to_message.from_user.id][1]}", parse_mode=None)

    if txt:
        for kw, rep in (await get_filters(cid)).items():
            if kw in txt.lower():
                await m.reply(rep, parse_mode=None); break

    if await _is_adm(m) or await is_approved(cid, uid):
        raise SkipHandler()

    s = await get_chat_settings(cid)
    fl = s.get("flood_limit", 0)
    if fl > 0:
        now = time.time()
        ts = [t for t in FLOOD_TRACKER.get((cid, uid), []) if now - t < 4] + [now]
        FLOOD_TRACKER[(cid, uid)] = ts
        if len(ts) > fl:
            FLOOD_TRACKER[(cid, uid)] = []
            await _punish(m.bot, cid, uid, FLOOD_MODES.get(cid, "mute"))
            await m.answer(f"🌊 {m.from_user.full_name} punished for flooding!", parse_mode=None)
            return

    if txt:
        low = txt.lower()
        for w in await get_blacklists(cid):
            if re.search(re.escape(w).replace(r"\*", ".*"), low):
                try: await m.delete()
                except Exception: pass
                await _punish(m.bot, cid, uid, BL_MODES.get(cid, "del"))
                return

    locks = await get_locks(cid)
    if locks and (
        "all" in locks or ("stickers" in locks and m.sticker) or ("gif" in locks and m.animation)
        or ("photo" in locks and m.photo) or ("video" in locks and m.video) or ("voice" in locks and m.voice)
        or ("document" in locks and m.document) or ("forwards" in locks and (m.forward_date or m.forward_origin))
        or ("media" in locks and (m.photo or m.video or m.animation or m.document))
        or (("links" in locks or "url" in locks) and ("http://" in txt or "https://" in txt or "t.me/" in txt))
        or ("cjk" in locks and re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", txt))
        or ("cyrillic" in locks and re.search(r"[\u0400-\u04FF]", txt))
    ):
        try: await m.delete()
        except Exception: pass
        return

    raise SkipHandler()
import time, uuid
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_profile
from RUKA.utils.db import (
    approve_user, unapprove_user, is_approved, get_approved,
    set_log_channel, unset_log_channel, get_log_channel,
    create_fed, join_fed, get_chat_fed, fban_user, funban_user
)

router = Router()
CHAT_LOCKS, CHAT_RULES, CHAT_NOTES, USER_CONNECTED, AFK_USERS = {}, {}, {}, {}, {}
CHAT_WARNS, WARN_LIMITS, CHAT_BLACKLIST, FLOOD_LIMITS, FLOOD_TRACKER = {}, {}, {}, {}, {}


async def _is_adm(message: Message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return False
    m = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return m.status in ("creator", "administrator")


async def _log(bot, chat_id: int, text: str):
    lid = await get_log_channel(chat_id)
    if lid:
        try:
            await bot.send_message(lid, text, parse_mode=None)
        except Exception:
            pass


# --- 1. Approval System (/approve, /unapprove, /approved) ---
@router.message(Command("approve", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def approve_cmd(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    t = message.reply_to_message.from_user
    await approve_user(message.chat.id, t.id)
    await message.answer(f"✅ **Approved** {t.full_name}! They bypass locks, antiflood & blacklists.", parse_mode=None)


@router.message(Command("unapprove", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def unapprove_cmd(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    t = message.reply_to_message.from_user
    await unapprove_user(message.chat.id, t.id)
    await message.answer(f"❌ **Unapproved** {t.full_name}.", parse_mode=None)


@router.message(Command("approved", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def approved_list(message: Message):
    uids = await get_approved(message.chat.id)
    await message.answer("✅ **Approved Users:**\n" + "\n".join(f"• `{u}`" for u in uids) if uids else "No approved users.")


# --- 2. Interactive Reports (/report or @admin) ---
@router.message(Command("report", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
@router.message(F.text.lower().contains("@admin"), F.chat.type.in_({"group", "supergroup"}))
async def report_cmd(message: Message):
    if not message.reply_to_message:
        return await message.answer("Reply to a rule-breaker's message to report them!")
    t = message.reply_to_message.from_user
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔨 Ban", callback_data=f"rep_ban_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🔇 Mute", callback_data=f"rep_mute_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="🗑️ Del", callback_data=f"rep_del_{t.id}_{message.reply_to_message.message_id}"),
        InlineKeyboardButton(text="✅ Dismiss", callback_data="rep_dismiss_0_0"),
    ]])
    await message.answer(f"🚨 **Reported** {t.full_name} (`{t.id}`) to Admins!", reply_markup=btn, parse_mode=None)


@router.callback_query(F.data.startswith("rep_"))
async def report_cb(query: CallbackQuery):
    m = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
    if m.status not in ("creator", "administrator"):
        return await query.answer("❌ Admins only!", show_alert=True)
    _, act, uid, mid = query.data.split("_")
    cid, uid, mid = query.message.chat.id, int(uid), int(mid)
    if act == "ban":
        await query.bot.ban_chat_member(cid, uid)
        await query.message.edit_text(f"🔨 Banned `{uid}` by {query.from_user.full_name}", parse_mode=None)
    elif act == "mute":
        await query.bot.restrict_chat_member(cid, uid, ChatPermissions(can_send_messages=False))
        await query.message.edit_text(f"🔇 Muted `{uid}` by {query.from_user.full_name}", parse_mode=None)
    elif act == "del":
        await query.bot.delete_message(cid, mid)
        await query.message.edit_text(f"🗑️ Deleted message by {query.from_user.full_name}", parse_mode=None)
    else:
        await query.message.edit_text("✅ Report dismissed.")
    await query.answer()


# --- 3. Log Channels (/setlog, /unsetlog, /logchannel) ---
@router.message(Command("setlog", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def setlog_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.answer("Usage: `/setlog -1001234567890`")
    await set_log_channel(message.chat.id, int(parts[1]))
    await message.answer(f"📜 Log channel set to `{parts[1]}`!")


@router.message(Command("unsetlog", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def unsetlog_cmd(message: Message):
    if not await _is_adm(message):
        return
    await unset_log_channel(message.chat.id)
    await message.answer("📜 Log channel removed.")


@router.message(Command("logchannel", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def getlog_cmd(message: Message):
    lid = await get_log_channel(message.chat.id)
    await message.answer(f"📜 Current Log Channel: `{lid}`" if lid else "No log channel set.")


# --- 4. Federations (/newfed, /joinfed, /fban, /funban) ---
@router.message(Command("newfed", prefix="/!"))
async def newfed_cmd(message: Message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/newfed <Fed Name>`")
    fid = str(uuid.uuid4())[:8]
    await create_fed(fid, parts[1], message.from_user.id)
    await message.answer(f"🌐 **Federation Created!**\nName: `{parts[1]}`\nFed ID: `{fid}`\nUse `/joinfed {fid}` in your groups!")


@router.message(Command("joinfed", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def joinfed_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/joinfed <fed_id>`")
    await join_fed(message.chat.id, parts[1])
    await message.answer(f"🌐 Joined Federation `{parts[1]}`!")


@router.message(Command("fban", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def fban_cmd(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    fid = await get_chat_fed(message.chat.id)
    if not fid:
        return await message.answer("❌ This group is not in a federation!")
    t = message.reply_to_message.from_user
    reason = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else "Fed Banned"
    await fban_user(fid, t.id, reason)
    await message.bot.ban_chat_member(message.chat.id, t.id)
    await message.answer(f"🌐 **Fed-Banned** {t.full_name} in `{fid}`!", parse_mode=None)


@router.message(Command("funban", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def funban_cmd(message: Message):
    if not await _is_adm(message):
        return
    fid = await get_chat_fed(message.chat.id)
    parts = message.text.split()
    if not fid or len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Usage: `/funban <user_id>`")
    await funban_user(fid, int(parts[1]))
    await message.answer(f"🌸 **Fed-Unbanned** `{parts[1]}`!")


# --- 5. Warns, Locks, Blacklist, Antiflood, Nightmode ---
@router.message(Command("warn", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def warn_user(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    t = message.reply_to_message.from_user
    key = (message.chat.id, t.id)
    warns = CHAT_WARNS.get(key, 0) + 1
    limit = WARN_LIMITS.get(message.chat.id, 3)
    if warns >= limit:
        CHAT_WARNS[key] = 0
        await message.bot.ban_chat_member(message.chat.id, t.id)
        await _log(message.bot, message.chat.id, f"🔨 Auto-banned {t.full_name} ({limit}/{limit} warns)")
        return await message.answer(f"🔨 {t.full_name} reached **{limit}/{limit} warns** and was **BANNED**!", parse_mode=None)
    CHAT_WARNS[key] = warns
    await _log(message.bot, message.chat.id, f"⚠️ Warned {t.full_name} ({warns}/{limit})")
    await message.answer(f"⚠️ **Warned** {t.full_name}! (`{warns}/{limit}`)", parse_mode=None)


@router.message(Command("unwarn", "resetwarns", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def unwarn_user(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    CHAT_WARNS[(message.chat.id, message.reply_to_message.from_user.id)] = 0
    await message.answer("✨ Warns cleared!")


@router.message(Command("warns", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def check_warns(message: Message):
    t = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.answer(f"⚠️ {t.full_name}: `{CHAT_WARNS.get((message.chat.id, t.id), 0)}/{WARN_LIMITS.get(message.chat.id, 3)}` warns.", parse_mode=None)


@router.message(Command("setwarnlimit", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def set_warn_limit(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        WARN_LIMITS[message.chat.id] = max(1, int(parts[1]))
        await message.answer(f"⚙️ Warn limit set to **{WARN_LIMITS[message.chat.id]}**!")


@router.message(Command("antiflood", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def set_antiflood(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) > 1 and parts[1].isdigit():
        FLOOD_LIMITS[message.chat.id] = int(parts[1])
        await message.answer(f"🌊 Anti-Flood: `{parts[1]} msgs/4s`")


@router.message(Command("blacklist", "unblacklist", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def bl_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return
    w = parts[1].lower()
    if message.text[1:].startswith("un"):
        CHAT_BLACKLIST.get(message.chat.id, set()).discard(w)
        await message.answer(f"✅ Unblacklisted `{w}`")
    else:
        CHAT_BLACKLIST.setdefault(message.chat.id, set()).add(w)
        await message.answer(f"🚫 Blacklisted `{w}`")


@router.message(Command("lock", "unlock", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def lock_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/lock links | stickers | forwards | media | all`")
    lt = parts[1].lower()
    if message.text[1:].startswith("un"):
        CHAT_LOCKS.get(message.chat.id, set()).discard(lt)
        await message.answer(f"🔓 Unlocked **{lt}**!")
    else:
        CHAT_LOCKS.setdefault(message.chat.id, set()).add(lt)
        await message.answer(f"🔒 Locked **{lt}**!")


@router.message(Command("locks", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def list_locks(message: Message):
    locks = CHAT_LOCKS.get(message.chat.id, set())
    await message.answer("🔒 **Locks:** " + ", ".join(locks) if locks else "🔓 No locks active.")


@router.message(Command("nightmode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def nightmode_cmd(message: Message):
    if not await _is_adm(message):
        return
    mode = message.text.split()[1].lower() if len(message.text.split()) > 1 else "on"
    locks = CHAT_LOCKS.setdefault(message.chat.id, set())
    if mode == "on":
        locks.update(["media", "stickers", "links"])
        await message.answer("🌙 **Night Mode ON!**")
    else:
        locks.difference_update(["media", "stickers", "links"])
        await message.answer("☀️ **Night Mode OFF!**")


# --- 6. Rules, Notes, Connect, Info, ID, Ping, AFK ---
@router.message(Command("setrules", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def set_rules(message: Message):
    if await _is_adm(message) and len(message.text.split()) > 1:
        CHAT_RULES[message.chat.id] = message.text.split(None, 1)[1]
        await message.answer("📜 Rules saved!")


@router.message(Command("rules", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def get_rules(message: Message):
    r = CHAT_RULES.get(message.chat.id)
    await message.answer(f"📜 **Rules:**\n\n{r}" if r else "📜 No rules set!")


@router.message(Command("save", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def save_note(message: Message):
    parts = message.text.split(None, 2)
    if await _is_adm(message) and len(parts) >= 3:
        CHAT_NOTES.setdefault(message.chat.id, {})[parts[1].lower()] = parts[2]
        await message.answer(f"📝 Saved `{parts[1].lower()}`!")


@router.message(Command("get", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def get_note(message: Message):
    parts = message.text.split()
    if len(parts) > 1:
        await message.answer(CHAT_NOTES.get(message.chat.id, {}).get(parts[1].lower(), "❌ Not found."))


@router.message(Command("notes", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def list_notes(message: Message):
    n = CHAT_NOTES.get(message.chat.id, {})
    await message.answer("📝 **Notes:** " + ", ".join(n.keys()) if n else "No notes.")


@router.message(Command("connect", prefix="/!"))
async def connect_chat(message: Message):
    if message.chat.type != "private":
        USER_CONNECTED[message.from_user.id] = message.chat.id
        return await message.answer(f"🔗 Connected to **{message.chat.title}**!")
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lstrip("-").isdigit():
        USER_CONNECTED[message.from_user.id] = int(parts[1])
        await message.answer(f"🔗 Connected to `{parts[1]}`!")


@router.message(Command("disconnect", prefix="/!"))
async def disconnect_chat(message: Message):
    USER_CONNECTED.pop(message.from_user.id, None)
    await message.answer("🔌 Disconnected.")


@router.message(Command("info", prefix="/!"))
async def user_info(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    await message.bot.send_chat_action(message.chat.id, "upload_photo")
    pfp_bytes = None
    try:
        photos = await message.bot.get_user_profile_photos(target.id, limit=1)
        if photos.total_count > 0:
            file = await message.bot.get_file(photos.photos[0][-1].file_id)
            pfp_bytes = BytesIO()
            await message.bot.download_file(file.file_path, pfp_bytes)
            pfp_bytes.seek(0)
    except Exception:
        pass
    img = generate_4k_profile(target.first_name, target.id, rank="Member", xp=50, pfp_bytes=pfp_bytes)
    await message.answer_photo(
        photo=BufferedInputFile(img.getvalue(), filename="info.jpg"),
        caption=f"👤 User Info\n• Name: {target.full_name}\n• ID: {target.id}\n• Username: @{target.username or 'None'}",
        parse_mode=None
    )


@router.message(Command("id", prefix="/!"))
async def get_id(message: Message):
    await message.answer(f"💬 Chat: `{message.chat.id}`\n👤 You: `{message.from_user.id}`")


@router.message(Command("ping", prefix="/!"))
async def ping_cmd(message: Message):
    s = time.time()
    m = await message.answer("🏓 Pinging...")
    await m.edit_text(f"💓 **Pong!** `{round((time.time() - s) * 1000, 2)}ms`")


@router.message(Command("afk", prefix="/!"))
async def set_afk(message: Message):
    reason = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else "Busy!"
    AFK_USERS[message.from_user.id] = (time.time(), reason)
    await message.answer(f"💤 {message.from_user.full_name} is **AFK**: `{reason}`", parse_mode=None)
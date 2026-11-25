import time
from io import BytesIO
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ChatPermissions, BufferedInputFile
from RUKA.utils.image_gen import generate_4k_profile

router = Router()

CHAT_LOCKS: dict[int, set[str]] = {}
CHAT_RULES: dict[int, str] = {}
CHAT_NOTES: dict[int, dict[str, str]] = {}
USER_CONNECTED: dict[int, int] = {}
AFK_USERS: dict[int, tuple[float, str]] = {}
CHAT_WARNS: dict[tuple[int, int], int] = {}
WARN_LIMITS: dict[int, int] = {}
CHAT_BLACKLIST: dict[int, set[str]] = {}
FLOOD_LIMITS: dict[int, int] = {}
FLOOD_TRACKER: dict[tuple[int, int], list[float]] = {}


async def _is_adm(message: Message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return False
    m = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return m.status in ("creator", "administrator")


@router.message(Command("warn"), F.chat.type.in_({"group", "supergroup"}))
async def warn_user(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    target = message.reply_to_message.from_user
    key = (message.chat.id, target.id)
    warns = CHAT_WARNS.get(key, 0) + 1
    limit = WARN_LIMITS.get(message.chat.id, 3)
    if warns >= limit:
        CHAT_WARNS[key] = 0
        await message.bot.ban_chat_member(message.chat.id, target.id)
        return await message.answer(f"🔨 {target.full_name} reached **{limit}/{limit} warns** and was **BANNED**!")
    CHAT_WARNS[key] = warns
    await message.answer(f"⚠️ **Warned** {target.full_name}! (`{warns}/{limit}`)")


@router.message(Command("unwarn"), F.chat.type.in_({"group", "supergroup"}))
async def unwarn_user(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    key = (message.chat.id, message.reply_to_message.from_user.id)
    CHAT_WARNS[key] = max(0, CHAT_WARNS.get(key, 0) - 1)
    await message.answer(f"🌸 Removed 1 warn! Now: `{CHAT_WARNS[key]}`")


@router.message(Command("warns"), F.chat.type.in_({"group", "supergroup"}))
async def check_warns(message: Message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warns = CHAT_WARNS.get((message.chat.id, target.id), 0)
    limit = WARN_LIMITS.get(message.chat.id, 3)
    await message.answer(f"⚠️ {target.full_name} has **`{warns}/{limit}`** warns.")


@router.message(Command("resetwarns"), F.chat.type.in_({"group", "supergroup"}))
async def reset_warns(message: Message):
    if not await _is_adm(message) or not message.reply_to_message:
        return
    CHAT_WARNS[(message.chat.id, message.reply_to_message.from_user.id)] = 0
    await message.answer("✨ Reset all warns!")


@router.message(Command("setwarnlimit"), F.chat.type.in_({"group", "supergroup"}))
async def set_warn_limit(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Usage: `/setwarnlimit 3`")
    WARN_LIMITS[message.chat.id] = max(1, int(parts[1]))
    await message.answer(f"⚙️ Warn limit set to **{WARN_LIMITS[message.chat.id]}**!")


@router.message(Command("antiflood"), F.chat.type.in_({"group", "supergroup"}))
async def set_antiflood(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Usage: `/antiflood 5` (0 to disable)")
    limit = int(parts[1])
    FLOOD_LIMITS[message.chat.id] = limit
    await message.answer(f"🌊 Anti-Flood set to **{limit} msgs / 4s**!" if limit > 0 else "🌊 Anti-Flood disabled.")


@router.message(Command("blacklist"), F.chat.type.in_({"group", "supergroup"}))
async def add_blacklist(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/blacklist <word>`")
    CHAT_BLACKLIST.setdefault(message.chat.id, set()).add(parts[1].lower())
    await message.answer(f"🚫 Added **`{parts[1].lower()}`** to blacklist!")


@router.message(Command("unblacklist"), F.chat.type.in_({"group", "supergroup"}))
async def rm_blacklist(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/unblacklist <word>`")
    CHAT_BLACKLIST.get(message.chat.id, set()).discard(parts[1].lower())
    await message.answer(f"✅ Removed **`{parts[1].lower()}`** from blacklist!")


@router.message(Command("blacklists"), F.chat.type.in_({"group", "supergroup"}))
async def list_blacklists(message: Message):
    words = CHAT_BLACKLIST.get(message.chat.id, set())
    await message.answer("🚫 **Blacklisted Words:**\n• " + "\n• ".join(words) if words else "No blacklisted words.")


@router.message(Command("lock"), F.chat.type.in_({"group", "supergroup"}))
async def lock_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/lock links | stickers | forwards | media | all`")
    ltype = parts[1].lower()
    CHAT_LOCKS.setdefault(message.chat.id, set()).add(ltype)
    await message.answer(f"🔒 Locked **{ltype}**!")


@router.message(Command("unlock"), F.chat.type.in_({"group", "supergroup"}))
async def unlock_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/unlock links | stickers | forwards | media | all`")
    CHAT_LOCKS.get(message.chat.id, set()).discard(parts[1].lower())
    await message.answer(f"🔓 Unlocked **{parts[1].lower()}**!")


@router.message(Command("locks"), F.chat.type.in_({"group", "supergroup"}))
async def list_locks(message: Message):
    locks = CHAT_LOCKS.get(message.chat.id, set())
    await message.answer("🔒 **Active Locks:**\n• " + "\n• ".join(locks) if locks else "🔓 No locks active.")


@router.message(Command("nightmode"), F.chat.type.in_({"group", "supergroup"}))
async def nightmode_cmd(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    mode = parts[1].lower() if len(parts) > 1 else "on"
    locks = CHAT_LOCKS.setdefault(message.chat.id, set())
    if mode == "on":
        locks.update(["media", "stickers", "links"])
        await message.answer("🌙 **Night Mode ON!** Media, stickers & links are locked~")
    else:
        locks.difference_update(["media", "stickers", "links"])
        await message.answer("☀️ **Night Mode OFF!** Good morning~")


@router.message(Command("setrules"), F.chat.type.in_({"group", "supergroup"}))
async def set_rules(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/setrules <rules>`")
    CHAT_RULES[message.chat.id] = parts[1]
    await message.answer("📜 Group rules saved!")


@router.message(Command("rules"), F.chat.type.in_({"group", "supergroup"}))
async def get_rules(message: Message):
    rules = CHAT_RULES.get(message.chat.id)
    await message.answer(f"📜 **{message.chat.title} Rules:**\n\n{rules}" if rules else "📜 No rules set yet!")


@router.message(Command("save"), F.chat.type.in_({"group", "supergroup"}))
async def save_note(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/save <name> <text>`")
    CHAT_NOTES.setdefault(message.chat.id, {})[parts[1].lower()] = parts[2]
    await message.answer(f"📝 Saved note **`{parts[1].lower()}`**!")


@router.message(Command("get"), F.chat.type.in_({"group", "supergroup"}))
async def get_note(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/get <name>`")
    note = CHAT_NOTES.get(message.chat.id, {}).get(parts[1].lower())
    await message.answer(note if note else "❌ Note not found.")


@router.message(Command("notes"), F.chat.type.in_({"group", "supergroup"}))
async def list_notes(message: Message):
    notes = CHAT_NOTES.get(message.chat.id, {})
    await message.answer("📝 **Saved Notes:**\n• " + "\n• ".join(notes.keys()) if notes else "📝 No notes saved.")


@router.message(Command("clear"), F.chat.type.in_({"group", "supergroup"}))
async def clear_note(message: Message):
    if not await _is_adm(message):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/clear <name>`")
    CHAT_NOTES.get(message.chat.id, {}).pop(parts[1].lower(), None)
    await message.answer("🗑️ Note deleted!")


@router.message(Command("connect"))
async def connect_chat(message: Message):
    if message.chat.type != "private":
        USER_CONNECTED[message.from_user.id] = message.chat.id
        return await message.answer(f"🔗 Connected you to **{message.chat.title}**!")
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return await message.answer("Usage in PM: `/connect -1001234567890`")
    USER_CONNECTED[message.from_user.id] = int(parts[1])
    await message.answer(f"🔗 Connected to `{parts[1]}`!")


@router.message(Command("disconnect"))
async def disconnect_chat(message: Message):
    USER_CONNECTED.pop(message.from_user.id, None)
    await message.answer("🔌 Disconnected from group.")


@router.message(Command("connection"))
async def check_connection(message: Message):
    cid = USER_CONNECTED.get(message.from_user.id)
    await message.answer(f"🔗 Connected to: `{cid}`" if cid else "❌ Not connected to any group.")


@router.message(Command("info"))
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
    photo = BufferedInputFile(img.getvalue(), filename="info.jpg")
    await message.answer_photo(
        photo=photo,
        caption=f"👤 User Info\n• Name: {target.full_name}\n• ID: {target.id}\n• Username: @{target.username or 'None'}",
        parse_mode=None
    )


@router.message(Command("id"))
async def get_id(message: Message):
    text = f"💬 **Chat ID:** `{message.chat.id}`\n👤 **Your ID:** `{message.from_user.id}`"
    if message.reply_to_message and message.reply_to_message.from_user:
        text += f"\n🎯 **Replied ID:** `{message.reply_to_message.from_user.id}`"
    await message.answer(text)


@router.message(Command("ping"))
async def ping_cmd(message: Message):
    start = time.time()
    m = await message.answer("🏓 Pinging...")
    await m.edit_text(f"💓 **Pong!** `{round((time.time() - start) * 1000, 2)}ms`")


@router.message(Command("afk"))
async def set_afk(message: Message):
    parts = message.text.split(None, 1)
    reason = parts[1] if len(parts) > 1 else "Busy!"
    AFK_USERS[message.from_user.id] = (time.time(), reason)
    await message.answer(f"💤 {message.from_user.full_name} is now **AFK**: `{reason}`")
import time
from pyrogram import Client, filters
from pyrogram.types import ChatPermissions
from ..utils.admin import admin
from ..utils.bot_admin import botAdmin
from ..utils.group_only import groupOnly
from ..utils.chat_action import chatAction
from ..utils.image_gen import generate_4k_profile

# In-memory stores
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


# --- 1. Warn System (/warn, /unwarn, /warns, /resetwarns, /setwarnlimit) ---
@Client.on_message(filters.command("warn") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def warn_user(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("Reply to a user to warn them!")
    target = message.reply_to_message.from_user
    key = (message.chat.id, target.id)
    warns = CHAT_WARNS.get(key, 0) + 1
    limit = WARN_LIMITS.get(message.chat.id, 3)

    if warns >= limit:
        CHAT_WARNS[key] = 0
        await client.ban_chat_member(message.chat.id, target.id)
        return await message.reply_text(f"🔨 {target.mention} reached **{limit}/{limit} warns** and has been **BANNED**!")

    CHAT_WARNS[key] = warns
    await message.reply_text(f"⚠️ **Warned** {target.mention}! (`{warns}/{limit}`)")


@Client.on_message(filters.command("unwarn") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
async def unwarn_user(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("Reply to a user to remove a warn!")
    key = (message.chat.id, message.reply_to_message.from_user.id)
    CHAT_WARNS[key] = max(0, CHAT_WARNS.get(key, 0) - 1)
    await message.reply_text(f"🌸 Removed 1 warn from {message.reply_to_message.from_user.mention}! Now: `{CHAT_WARNS[key]}`")


@Client.on_message(filters.command("warns") & filters.group)
async def check_warns(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    warns = CHAT_WARNS.get((message.chat.id, target.id), 0)
    limit = WARN_LIMITS.get(message.chat.id, 3)
    await message.reply_text(f"⚠️ {target.mention} has **`{warns}/{limit}`** warns.")


@Client.on_message(filters.command("resetwarns") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
async def reset_warns(client, message):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("Reply to a user to reset their warns!")
    CHAT_WARNS[(message.chat.id, message.reply_to_message.from_user.id)] = 0
    await message.reply_text(f"✨ Reset all warns for {message.reply_to_message.from_user.mention}!")


@Client.on_message(filters.command("setwarnlimit") & filters.group)
@groupOnly()
@admin(msg=True)
async def set_warn_limit(client, message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: `/setwarnlimit 3`")
    WARN_LIMITS[message.chat.id] = max(1, int(message.command[1]))
    await message.reply_text(f"⚙️ Warn limit set to **{WARN_LIMITS[message.chat.id]}**!")


# --- 2. Anti-Flood & Word Blacklist ---
@Client.on_message(filters.command("antiflood") & filters.group)
@groupOnly()
@admin(msg=True)
async def set_antiflood(client, message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text("Usage: `/antiflood 5` (0 to disable)")
    limit = int(message.command[1])
    FLOOD_LIMITS[message.chat.id] = limit
    await message.reply_text(f"🌊 Anti-Flood set to **{limit} msgs / 4s**!" if limit > 0 else "🌊 Anti-Flood disabled.")


@Client.on_message(filters.command("blacklist") & filters.group)
@groupOnly()
@admin(msg=True)
async def add_blacklist(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/blacklist <word>`")
    word = message.command[1].lower()
    CHAT_BLACKLIST.setdefault(message.chat.id, set()).add(word)
    await message.reply_text(f"🚫 Added **`{word}`** to the blacklist!")


@Client.on_message(filters.command("unblacklist") & filters.group)
@groupOnly()
@admin(msg=True)
async def rm_blacklist(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/unblacklist <word>`")
    word = message.command[1].lower()
    CHAT_BLACKLIST.get(message.chat.id, set()).discard(word)
    await message.reply_text(f"✅ Removed **`{word}`** from the blacklist!")


@Client.on_message(filters.command("blacklists") & filters.group)
async def list_blacklists(client, message):
    words = CHAT_BLACKLIST.get(message.chat.id, set())
    await message.reply_text("🚫 **Blacklisted Words:**\n• " + "\n• ".join(words) if words else "No blacklisted words.")


# --- 3. Locks & Night Mode ---
@Client.on_message(filters.command("lock") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
async def lock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/lock links | stickers | forwards | media | all`")
    ltype = message.command[1].lower()
    if ltype not in ("links", "stickers", "forwards", "media", "all"):
        return await message.reply_text("Valid locks: `links`, `stickers`, `forwards`, `media`, `all`")
    CHAT_LOCKS.setdefault(message.chat.id, set()).add(ltype)
    await message.reply_text(f"🔒 Locked **{ltype}**! Ruka will delete them~")


@Client.on_message(filters.command("unlock") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
async def unlock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/unlock links | stickers | forwards | media | all`")
    ltype = message.command[1].lower()
    CHAT_LOCKS.get(message.chat.id, set()).discard(ltype)
    await message.reply_text(f"🔓 Unlocked **{ltype}**!")


@Client.on_message(filters.command("locks") & filters.group)
async def list_locks(client, message):
    locks = CHAT_LOCKS.get(message.chat.id, set())
    await message.reply_text("🔒 **Active Locks:**\n• " + "\n• ".join(locks) if locks else "🔓 No locks active.")


@Client.on_message(filters.command("nightmode") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
async def nightmode_cmd(client, message):
    mode = message.command[1].lower() if len(message.command) > 1 else "on"
    locks = CHAT_LOCKS.setdefault(message.chat.id, set())
    if mode == "on":
        locks.update(["media", "stickers", "links"])
        await message.reply_text("🌙 **Night Mode ON!** Media, stickers & links are locked until morning~")
    else:
        locks.difference_update(["media", "stickers", "links"])
        await message.reply_text("☀️ **Night Mode OFF!** Good morning everyone~")


# --- Auto-Enforce Locks, Blacklist & Anti-Flood (group=2) ---
@Client.on_message(filters.group, group=2)
async def enforce_security(client, message):
    if not message.from_user or message.from_user.is_bot:
        return
    cid, uid = message.chat.id, message.from_user.id

    try:
        member = await client.get_chat_member(cid, uid)
        if member.status.name in ("ADMINISTRATOR", "OWNER"):
            return
    except Exception:
        return

    # Anti-Flood
    flimit = FLOOD_LIMITS.get(cid, 0)
    if flimit > 0:
        now = time.time()
        times = [t for t in FLOOD_TRACKER.get((cid, uid), []) if now - t < 4]
        times.append(now)
        FLOOD_TRACKER[(cid, uid)] = times
        if len(times) > flimit:
            FLOOD_TRACKER[(cid, uid)] = []
            await client.restrict_chat_member(cid, uid, ChatPermissions())
            return await message.reply_text(f"🌊 {message.from_user.mention} was **muted** for flooding!")

    # Blacklist
    if message.text:
        lower = message.text.lower()
        for w in CHAT_BLACKLIST.get(cid, set()):
            if w in lower:
                return await message.delete()

    # Locks
    locks = CHAT_LOCKS.get(cid, set())
    if "all" in locks:
        return await message.delete()
    if "links" in locks and message.text and ("http://" in message.text or "https://" in message.text or "t.me/" in message.text):
        return await message.delete()
    if "stickers" in locks and message.sticker:
        return await message.delete()
    if "forwards" in locks and message.forward_date:
        return await message.delete()
    if "media" in locks and (message.photo or message.video or message.animation or message.document):
        return await message.delete()


# --- 4. Rules & Notes ---
@Client.on_message(filters.command("setrules") & filters.group)
@groupOnly()
@admin(msg=True)
async def set_rules(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/setrules <your group rules>`")
    CHAT_RULES[message.chat.id] = message.text.split(None, 1)[1]
    await message.reply_text("📜 Group rules saved! Members can view them with `/rules`.")


@Client.on_message(filters.command("rules") & filters.group)
async def get_rules(client, message):
    rules = CHAT_RULES.get(message.chat.id)
    await message.reply_text(f"📜 **{message.chat.title} Rules:**\n\n{rules}" if rules else "📜 No rules set yet!")


@Client.on_message(filters.command("save") & filters.group)
@groupOnly()
@admin(msg=True)
async def save_note(client, message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/save <name> <text>`")
    name = message.command[1].lower()
    CHAT_NOTES.setdefault(message.chat.id, {})[name] = message.text.split(None, 2)[2]
    await message.reply_text(f"📝 Saved note **`{name}`**!")


@Client.on_message(filters.command("get") & filters.group)
async def get_note(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/get <name>`")
    note = CHAT_NOTES.get(message.chat.id, {}).get(message.command[1].lower())
    await message.reply_text(note if note else "❌ Note not found.")


@Client.on_message(filters.command("notes") & filters.group)
async def list_notes(client, message):
    notes = CHAT_NOTES.get(message.chat.id, {})
    await message.reply_text("📝 **Saved Notes:**\n• " + "\n• ".join(notes.keys()) if notes else "📝 No notes saved.")


@Client.on_message(filters.command("clear") & filters.group)
@groupOnly()
@admin(msg=True)
async def clear_note(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/clear <name>`")
    CHAT_NOTES.get(message.chat.id, {}).pop(message.command[1].lower(), None)
    await message.reply_text("🗑️ Note deleted!")


# --- 5. Connect System ---
@Client.on_message(filters.command("connect"))
async def connect_chat(client, message):
    if message.chat.type.name != "PRIVATE":
        USER_CONNECTED[message.from_user.id] = message.chat.id
        return await message.reply_text(f"🔗 Connected you to **{message.chat.title}**!")
    if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage in PM: `/connect -1001234567890`")
    USER_CONNECTED[message.from_user.id] = int(message.command[1])
    await message.reply_text(f"🔗 Connected to `{message.command[1]}`!")


@Client.on_message(filters.command("disconnect"))
async def disconnect_chat(client, message):
    USER_CONNECTED.pop(message.from_user.id, None)
    await message.reply_text("🔌 Disconnected from group.")


@Client.on_message(filters.command("connection"))
async def check_connection(client, message):
    cid = USER_CONNECTED.get(message.from_user.id)
    await message.reply_text(f"🔗 Connected to: `{cid}`" if cid else "❌ Not connected to any group.")


# --- 6. Utility & 4K Info ---
@Client.on_message(filters.command("info"))
@chatAction("upload_photo")
async def user_info(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pfp_bytes = await client.download_media(target.photo.big_file_id, in_memory=True) if target.photo else None
    img = generate_4k_profile(target.first_name, target.id, rank="Member", xp=50, pfp_bytes=pfp_bytes)
    await message.reply_photo(
        photo=img,
        caption=f"👤 **User Info**\n• Name: {target.mention}\n• ID: `{target.id}`\n• Username: @{target.username or 'None'}"
    )


@Client.on_message(filters.command("id"))
async def get_id(client, message):
    text = f"💬 **Chat ID:** `{message.chat.id}`\n👤 **Your ID:** `{message.from_user.id}`"
    if message.reply_to_message and message.reply_to_message.from_user:
        text += f"\n🎯 **Replied ID:** `{message.reply_to_message.from_user.id}`"
    await message.reply_text(text)


@Client.on_message(filters.command("ping"))
async def ping_cmd(client, message):
    start = time.time()
    m = await message.reply_text("🏓 Pinging...")
    await m.edit_text(f"💓 **Pong!** `{round((time.time() - start) * 1000, 2)}ms` — Ruka's heart is beating fast!")


@Client.on_message(filters.command("afk"))
async def set_afk(client, message):
    reason = message.text.split(None, 1)[1] if len(message.command) > 1 else "Busy!"
    AFK_USERS[message.from_user.id] = (time.time(), reason)
    await message.reply_text(f"💤 {message.from_user.mention} is now **AFK**: `{reason}`")


@Client.on_message(filters.group & ~filters.command("afk"), group=3)
async def afk_watcher(client, message):
    if not message.from_user:
        return
    if message.from_user.id in AFK_USERS:
        AFK_USERS.pop(message.from_user.id)
        await message.reply_text(f"🌸 Welcome back, {message.from_user.mention}! You're no longer AFK.")
    elif message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id in AFK_USERS:
        _, reason = AFK_USERS[message.reply_to_message.from_user.id]
        await message.reply_text(f"💤 {message.reply_to_message.from_user.first_name} is **AFK**: `{reason}`")
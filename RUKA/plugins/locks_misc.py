import time
from pyrogram import Client, filters
from ..utils import admin, botAdmin, groupOnly, chatAction
from ..utils.image_gen import generate_4k_profile

# In-memory stores (fast & zero-setup)
CHAT_LOCKS: dict[int, set[str]] = {}
CHAT_RULES: dict[int, str] = {}
CHAT_NOTES: dict[int, dict[str, str]] = {}
USER_CONNECTED: dict[int, int] = {}
AFK_USERS: dict[int, tuple[float, str]] = {}


# --- 1. Locks & Anti-Link ---
@Client.on_message(filters.command("lock") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
async def lock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/lock links | stickers | forwards | all`")
    ltype = message.command[1].lower()
    if ltype not in ("links", "stickers", "forwards", "all"):
        return await message.reply_text("Valid locks: `links`, `stickers`, `forwards`, `all`")
    CHAT_LOCKS.setdefault(message.chat.id, set()).add(ltype)
    await message.reply_text(f"🔒 Locked **{ltype}**! Ruka will delete them~")


@Client.on_message(filters.command("unlock") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
async def unlock_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/unlock links | stickers | forwards | all`")
    ltype = message.command[1].lower()
    CHAT_LOCKS.get(message.chat.id, set()).discard(ltype)
    await message.reply_text(f"🔓 Unlocked **{ltype}**!")


@Client.on_message(filters.command("locks") & filters.group)
async def list_locks(client, message):
    locks = CHAT_LOCKS.get(message.chat.id, set())
    if not locks:
        return await message.reply_text("🔓 No locks are currently active in this group.")
    await message.reply_text("🔒 **Active Locks:**\n• " + "\n• ".join(locks))


# Auto-enforce locks (group=2 so it doesn't block commands)
@Client.on_message(filters.group, group=2)
async def enforce_locks(client, message):
    locks = CHAT_LOCKS.get(message.chat.id)
    if not locks or not message.from_user:
        return
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status.name in ("ADMINISTRATOR", "OWNER"):
            return
    except Exception:
        return

    if "all" in locks:
        return await message.delete()
    if "links" in locks and message.text and ("http://" in message.text or "https://" in message.text or "t.me/" in message.text):
        return await message.delete()
    if "stickers" in locks and message.sticker:
        return await message.delete()
    if "forwards" in locks and message.forward_date:
        return await message.delete()


# --- 2. Rules & Notes ---
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
    if not rules:
        return await message.reply_text("📜 No rules set yet! Admins can set them with `/setrules`.")
    await message.reply_text(f"📜 **{message.chat.title} Rules:**\n\n{rules}")


@Client.on_message(filters.command("save") & filters.group)
@groupOnly()
@admin(msg=True)
async def save_note(client, message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/save <name> <text>`")
    name = message.command[1].lower()
    text = message.text.split(None, 2)[2]
    CHAT_NOTES.setdefault(message.chat.id, {})[name] = text
    await message.reply_text(f"📝 Saved note **`{name}`**!")


@Client.on_message(filters.command("get") & filters.group)
async def get_note(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/get <name>`")
    name = message.command[1].lower()
    note = CHAT_NOTES.get(message.chat.id, {}).get(name)
    if not note:
        return await message.reply_text(f"❌ Note `{name}` not found.")
    await message.reply_text(note)


@Client.on_message(filters.command("notes") & filters.group)
async def list_notes(client, message):
    notes = CHAT_NOTES.get(message.chat.id, {})
    if not notes:
        return await message.reply_text("📝 No notes saved in this group.")
    await message.reply_text("📝 **Saved Notes:**\n• " + "\n• ".join(notes.keys()))


@Client.on_message(filters.command("clear") & filters.group)
@groupOnly()
@admin(msg=True)
async def clear_note(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/clear <name>`")
    name = message.command[1].lower()
    CHAT_NOTES.get(message.chat.id, {}).pop(name, None)
    await message.reply_text(f"🗑️ Deleted note `{name}`!")


# --- 3. Connect System (Manage Group from PM) ---
@Client.on_message(filters.command("connect"))
async def connect_chat(client, message):
    if message.chat.type.name != "PRIVATE":
        USER_CONNECTED[message.from_user.id] = message.chat.id
        return await message.reply_text(f"🔗 Connected you to **{message.chat.title}**! You can now manage it from PM.")
    if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage in PM: `/connect -1001234567890`")
    cid = int(message.command[1])
    USER_CONNECTED[message.from_user.id] = cid
    await message.reply_text(f"🔗 Connected to `{cid}`!")


@Client.on_message(filters.command("disconnect"))
async def disconnect_chat(client, message):
    USER_CONNECTED.pop(message.from_user.id, None)
    await message.reply_text("🔌 Disconnected from group.")


@Client.on_message(filters.command("connection"))
async def check_connection(client, message):
    cid = USER_CONNECTED.get(message.from_user.id)
    await message.reply_text(f"🔗 Currently connected to: `{cid}`" if cid else "❌ Not connected to any group.")


# --- 4. Utility & 4K Info ---
@Client.on_message(filters.command("info"))
@chatAction("upload_photo")
async def user_info(client, message):
    target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
    pfp_bytes = None
    if target.photo:
        pfp_bytes = await client.download_media(target.photo.big_file_id, in_memory=True)
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
    ms = round((time.time() - start) * 1000, 2)
    await m.edit_text(f"💓 **Pong!** `{ms}ms` — Ruka's heart is beating fast!")


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
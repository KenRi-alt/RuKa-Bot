from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from ..utils.admin import admin
from ..utils.bot_admin import botAdmin
from ..utils.group_only import groupOnly
from ..utils.db import get_chat_settings, toggle_setting, add_filter, remove_filter, get_filters


def _settings_markup(s: dict):
    def icon(val: bool):
        return "✅" if val else "❌"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{icon(s['captcha'])} Join CAPTCHA", callback_data="set_captcha"),
            InlineKeyboardButton(f"{icon(s['welcome'])} 4K Welcome", callback_data="set_welcome"),
        ],
        [
            InlineKeyboardButton(f"{icon(s['antilink'])} Anti-Link", callback_data="set_antilink"),
            InlineKeyboardButton(f"{icon(s['nightmode'])} Night Mode", callback_data="set_nightmode"),
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="set_close")
        ]
    ])


# --- 1. /settings — Interactive Group Settings Panel (Saved in PostgreSQL!) ---
@Client.on_message(filters.command("settings") & filters.group)
@groupOnly()
@admin(msg=True)
async def settings_panel(client, message):
    s = await get_chat_settings(message.chat.id)
    await message.reply_text(
        f"⚙️ **{message.chat.title} — Ruka Settings**\n"
        f"*(Saved permanently in PostgreSQL)*\n\n"
        f"Tap any button below to toggle:",
        reply_markup=_settings_markup(s)
    )


@Client.on_callback_query(filters.regex(r"^set_"))
async def settings_callbacks(client, query):
    action = query.data.split("_")[1]
    if action == "close":
        return await query.message.delete()

    member = await client.get_chat_member(query.message.chat.id, query.from_user.id)
    if member.status.name not in ("ADMINISTRATOR", "OWNER"):
        return await query.answer("❌ Only admins can change settings!", show_alert=True)

    await toggle_setting(query.message.chat.id, action)
    s = await get_chat_settings(query.message.chat.id)
    await query.message.edit_reply_markup(_settings_markup(s))
    await query.answer(f"Updated {action}!")


# --- 2. Join CAPTCHA (Mute new members until they click "I'm Human") ---
@Client.on_message(filters.new_chat_members & filters.group, group=4)
async def captcha_join(client, message):
    s = await get_chat_settings(message.chat.id)
    if not s["captcha"]:
        return

    for user in message.new_chat_members:
        if user.is_bot:
            continue
        try:
            await client.restrict_chat_member(message.chat.id, user.id, ChatPermissions())
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("✅ I'm Human!", callback_data=f"cap_{user.id}")]])
            await message.reply_text(
                f"🛡️ **Verification Required!**\n{user.mention}, tap the button below to prove you're not a spam bot!",
                reply_markup=btn
            )
        except Exception:
            pass


@Client.on_callback_query(filters.regex(r"^cap_"))
async def captcha_verify(client, query):
    target_id = int(query.data.split("_")[1])
    if query.from_user.id != target_id:
        return await query.answer("❌ This button isn't for you!", show_alert=True)

    await client.restrict_chat_member(
        query.message.chat.id, target_id,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await query.message.edit_text(f"✅ {query.from_user.mention} is verified! Welcome~ 🌸")


# --- 3. Auto-Filters (/filter, /stop, /filters) ---
@Client.on_message(filters.command("filter") & filters.group)
@groupOnly()
@admin(msg=True)
async def add_filter_cmd(client, message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/filter <keyword> <reply>`")
    kw = message.command[1].lower()
    reply = message.text.split(None, 2)[2]
    await add_filter(message.chat.id, kw, reply)
    await message.reply_text(f"✨ Added filter for **`{kw}`**!")


@Client.on_message(filters.command("stop") & filters.group)
@groupOnly()
@admin(msg=True)
async def stop_filter_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/stop <keyword>`")
    kw = message.command[1].lower()
    await remove_filter(message.chat.id, kw)
    await message.reply_text(f"🗑️ Removed filter **`{kw}`**!")


@Client.on_message(filters.command("filters") & filters.group)
async def list_filters_cmd(client, message):
    flts = await get_filters(message.chat.id)
    if not flts:
        return await message.reply_text("📝 No active filters in this group.")
    await message.reply_text("📝 **Active Filters:**\n• " + "\n• ".join(flts.keys()))


@Client.on_message(filters.group & filters.text, group=5)
async def filter_watcher(client, message):
    if not message.text or message.text.startswith("/"):
        return
    flts = await get_filters(message.chat.id)
    lower = message.text.lower()
    for kw, reply in flts.items():
        if kw in lower:
            await message.reply_text(reply)
            break
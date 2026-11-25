from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA.utils.db import get_chat_settings, toggle_setting, add_filter, remove_filter, get_filters

router = Router()


def _settings_markup(s: dict):
    def icon(val: bool):
        return "✅" if val else "❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{icon(s['captcha'])} Join CAPTCHA", callback_data="set_captcha"),
            InlineKeyboardButton(text=f"{icon(s['welcome'])} 4K Welcome", callback_data="set_welcome"),
        ],
        [
            InlineKeyboardButton(text=f"{icon(s['antilink'])} Anti-Link", callback_data="set_antilink"),
            InlineKeyboardButton(text=f"{icon(s['nightmode'])} Night Mode", callback_data="set_nightmode"),
        ],
        [InlineKeyboardButton(text="❌ Close", callback_data="set_close")]
    ])


@router.message(Command("settings"), F.chat.type.in_({"group", "supergroup"}))
async def settings_panel(message: Message):
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("creator", "administrator"):
        return await message.answer("❌ Only admins can change settings!")
    s = await get_chat_settings(message.chat.id)
    await message.answer(
        f"⚙️ **{message.chat.title} — Ruka Settings**\n*(Saved permanently in PostgreSQL)*\n\nTap any button below to toggle:",
        reply_markup=_settings_markup(s)
    )


@router.callback_query(F.data.startswith("set_"))
async def settings_callbacks(query: CallbackQuery):
    action = query.data.split("_")[1]
    if action == "close":
        return await query.message.delete()
    member = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
    if member.status not in ("creator", "administrator"):
        return await query.answer("❌ Only admins can change settings!", show_alert=True)
    await toggle_setting(query.message.chat.id, action)
    s = await get_chat_settings(query.message.chat.id)
    await query.message.edit_reply_markup(reply_markup=_settings_markup(s))
    await query.answer(f"Updated {action}!")


@router.message(F.new_chat_members)
async def captcha_join(message: Message):
    s = await get_chat_settings(message.chat.id)
    if not s["captcha"]:
        return
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        try:
            await message.bot.restrict_chat_member(message.chat.id, user.id, ChatPermissions(can_send_messages=False))
            btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ I'm Human!", callback_data=f"cap_{user.id}")]])
            await message.answer(f"🛡️ **Verification Required!**\n{user.full_name}, tap below to prove you're human!", reply_markup=btn)
        except Exception:
            pass


@router.callback_query(F.data.startswith("cap_"))
async def captcha_verify(query: CallbackQuery):
    target_id = int(query.data.split("_")[1])
    if query.from_user.id != target_id:
        return await query.answer("❌ This button isn't for you!", show_alert=True)
    await query.bot.restrict_chat_member(
        query.message.chat.id, target_id,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await query.message.edit_text(f"✅ {query.from_user.full_name} is verified! Welcome~ 🌸")


@router.message(Command("filter"), F.chat.type.in_({"group", "supergroup"}))
async def add_filter_cmd(message: Message):
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("creator", "administrator"):
        return await message.answer("❌ Admins only!")
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/filter <keyword> <reply>`")
    await add_filter(message.chat.id, parts[1].lower(), parts[2])
    await message.answer(f"✨ Added filter for **`{parts[1].lower()}`**!")


@router.message(Command("stop"), F.chat.type.in_({"group", "supergroup"}))
async def stop_filter_cmd(message: Message):
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("creator", "administrator"):
        return await message.answer("❌ Admins only!")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/stop <keyword>`")
    await remove_filter(message.chat.id, parts[1].lower())
    await message.answer(f"🗑️ Removed filter **`{parts[1].lower()}`**!")


@router.message(Command("filters"), F.chat.type.in_({"group", "supergroup"}))
async def list_filters_cmd(message: Message):
    flts = await get_filters(message.chat.id)
    await message.answer("📝 **Active Filters:**\n• " + "\n• ".join(flts.keys()) if flts else "📝 No active filters.")
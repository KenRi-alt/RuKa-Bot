import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA.utils.db import (
    get_chat_settings, toggle_setting, add_filter, remove_filter, get_filters,
    disable_cmd, enable_cmd, get_disabled_cmds, get_chat_fed, is_fbanned, get_log_channel
)

router = Router()
PENDING_CAPTCHA: set[tuple[int, int]] = set()


async def _is_adm(message: Message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return False
    m = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    return m.status in ("creator", "administrator")


def _settings_markup(s: dict) -> InlineKeyboardMarkup:
    ic = lambda v: "✅" if v else "❌"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ic(s['captcha'])} CAPTCHA", callback_data="set_captcha"),
         InlineKeyboardButton(text=f"{ic(s['antiraid'])} Anti-Raid", callback_data="set_antiraid")],
        [InlineKeyboardButton(text=f"{ic(s['antilink'])} Anti-Link", callback_data="set_antilink"),
         InlineKeyboardButton(text=f"{ic(s['nightmode'])} Night Mode", callback_data="set_nightmode")],
        [InlineKeyboardButton(text=f"{ic(s['cleanservice'])} Clean Service", callback_data="set_cleanservice"),
         InlineKeyboardButton(text=f"{ic(s['cleancommand'])} Clean Cmds", callback_data="set_cleancommand")],
        [InlineKeyboardButton(text=f"{ic(s['welcome'])} Welcome", callback_data="set_welcome"),
         InlineKeyboardButton(text="❌ Close", callback_data="set_close")],
    ])


@router.message(Command("settings", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def settings_panel(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    s = await get_chat_settings(message.chat.id)
    await message.answer(f"⚙️ **{message.chat.title} — Settings**", reply_markup=_settings_markup(s))


@router.callback_query(F.data.startswith("set_"))
async def settings_callbacks(query: CallbackQuery):
    action = query.data.split("_")[1]
    if action == "close":
        return await query.message.delete()
    member = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
    if member.status not in ("creator", "administrator"):
        return await query.answer("❌ Admins only!", show_alert=True)

    new_val = await toggle_setting(query.message.chat.id, action)
    s = await get_chat_settings(query.message.chat.id)
    await query.message.edit_reply_markup(reply_markup=_settings_markup(s))
    await query.answer(f"{action.capitalize()} -> {'ON ✅' if new_val else 'OFF ❌'}")

    log_id = await get_log_channel(query.message.chat.id)
    if log_id:
        try:
            await query.bot.send_message(log_id, f"⚙️ {action} -> {'ON' if new_val else 'OFF'} in {query.message.chat.title} by {query.from_user.full_name}", parse_mode=None)
        except Exception:
            pass


@router.message(Command("antiraid", "cleanservice", "cleancommand", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def quick_toggle_cmd(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    cmd = message.text.split()[0].lstrip("/!").split("@")[0].lower()
    new_val = await toggle_setting(message.chat.id, cmd)
    await message.answer(f"🛡️ **{cmd.capitalize()}** is now **{'ON ✅' if new_val else 'OFF ❌'}**!")


@router.message(F.new_chat_members)
async def on_user_join(message: Message):
    cid = message.chat.id
    s = await get_chat_settings(cid)
    if s["cleanservice"]:
        try:
            await message.delete()
        except Exception:
            pass

    fed_id = await get_chat_fed(cid)
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        if fed_id:
            reason = await is_fbanned(fed_id, user.id)
            if reason:
                try:
                    await message.bot.ban_chat_member(cid, user.id)
                    await message.answer(f"🌐 **Fed-Banned User Blocked:** {user.full_name} (`{reason}`)")
                except Exception:
                    pass
                continue
        if s["antiraid"]:
            try:
                await message.bot.ban_chat_member(cid, user.id)
                await message.bot.unban_chat_member(cid, user.id)
            except Exception:
                pass
            continue
        if s["captcha"]:
            try:
                await message.bot.restrict_chat_member(cid, user.id, ChatPermissions(can_send_messages=False))
                PENDING_CAPTCHA.add((cid, user.id))
                btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ I'm Human!", callback_data=f"cap_{user.id}")]])
                cap_msg = await message.answer(f"🛡️ **Verify within 2 mins:** {user.full_name}", reply_markup=btn)
                asyncio.create_task(_captcha_timeout(message.bot, cid, user.id, cap_msg.message_id))
            except Exception:
                pass


async def _captcha_timeout(bot, cid: int, uid: int, msg_id: int):
    await asyncio.sleep(120)
    if (cid, uid) in PENDING_CAPTCHA:
        PENDING_CAPTCHA.discard((cid, uid))
        try:
            await bot.ban_chat_member(cid, uid)
            await bot.unban_chat_member(cid, uid)
            await bot.delete_message(cid, msg_id)
        except Exception:
            pass


@router.callback_query(F.data.startswith("cap_"))
async def captcha_verify(query: CallbackQuery):
    target_id = int(query.data.split("_")[1])
    if query.from_user.id != target_id:
        return await query.answer("❌ Not for you!", show_alert=True)
    PENDING_CAPTCHA.discard((query.message.chat.id, target_id))
    await query.bot.restrict_chat_member(
        query.message.chat.id, target_id,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await query.message.edit_text(f"✅ {query.from_user.full_name} verified! Welcome~ 🌸")


@router.message(F.left_chat_member | F.pinned_message | F.new_chat_title | F.new_chat_photo)
async def clean_service_msgs(message: Message):
    s = await get_chat_settings(message.chat.id)
    if s["cleanservice"]:
        try:
            await message.delete()
        except Exception:
            pass


@router.message(Command("disable", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def disable_command(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/disable gacha`")
    cmd = parts[1].lstrip("/!").lower()
    await disable_cmd(message.chat.id, cmd)
    await message.answer(f"🚫 Disabled `/{cmd}`.")


@router.message(Command("enable", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def enable_command(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/enable gacha`")
    cmd = parts[1].lstrip("/!").lower()
    await enable_cmd(message.chat.id, cmd)
    await message.answer(f"✅ Enabled `/{cmd}`.")


@router.message(Command("disabled", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def list_disabled(message: Message):
    cmds = await get_disabled_cmds(message.chat.id)
    await message.answer("🚫 **Disabled:**\n• " + "\n• ".join(cmds) if cmds else "✅ None disabled.")


@router.message(Command("filter", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def add_filter_cmd(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/filter <word> <reply>`")
    await add_filter(message.chat.id, parts[1].lower(), parts[2])
    await message.answer(f"✨ Filter added for `{parts[1].lower()}`!")


@router.message(Command("stop", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def stop_filter_cmd(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Usage: `/stop <word>`")
    await remove_filter(message.chat.id, parts[1].lower())
    await message.answer(f"🗑️ Filter `{parts[1].lower()}` removed!")


@router.message(Command("filters", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def list_filters_cmd(message: Message):
    flts = await get_filters(message.chat.id)
    await message.answer("📝 **Filters:**\n• " + "\n• ".join(flts.keys()) if flts else "📝 No active filters.")
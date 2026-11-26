import random, asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA.utils.db import (
    get_pool, get_chat_settings, toggle_setting, add_filter, remove_filter, get_filters,
    disable_cmd, enable_cmd, get_disabled_cmds, get_chat_fed, is_fbanned, get_log_channel
)

router = Router()
PENDING_CAPTCHA: set[tuple[int, int]] = set()
CAPTCHA_MODES: dict[int, str] = {}  # chat_id -> "button" | "math"


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


# --- 1. /settings Panel ---
@router.message(Command("settings", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def settings_panel(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    s = await get_chat_settings(message.chat.id)
    await message.answer(f"⚙️ **{message.chat.title} — Security & Settings**", reply_markup=_settings_markup(s))


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


# --- 2. Quick Toggles & CAPTCHA Mode ---
@router.message(Command("captcha", "antiraid", "cleanservice", "cleancommand", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def quick_toggle_cmd(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    cmd = message.text.split()[0].lstrip("/!").split("@")[0].lower()
    new_val = await toggle_setting(message.chat.id, cmd)
    await message.answer(f"🛡️ **{cmd.capitalize()}** is now **{'ON ✅' if new_val else 'OFF ❌'}**!")


@router.message(Command("captchamode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def captchamode_cmd(message: Message):
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    p = message.text.split()
    if len(p) > 1 and p[1].lower() in ("button", "math"):
        CAPTCHA_MODES[message.chat.id] = p[1].lower()
        return await message.answer(f"🛡️ CAPTCHA mode set to **{p[1].lower()}**!")
    await message.answer("Usage: `/captchamode button` or `/captchamode math`")


# --- 3. Join Handler: Fed-Ban + Anti-Raid + Button/Math CAPTCHA ---
@router.message(F.new_chat_members)
async def on_user_join(message: Message):
    cid = message.chat.id
    s = await get_chat_settings(cid)
    if s.get("cleanservice"):
        try:
            await message.delete()
        except Exception:
            pass

    fed_id = await get_chat_fed(cid)
    mode = CAPTCHA_MODES.get(cid, "button")

    for user in message.new_chat_members:
        if user.is_bot:
            continue
        if fed_id:
            reason = await is_fbanned(fed_id, user.id)
            if reason:
                try:
                    await message.bot.ban_chat_member(cid, user.id)
                    await message.answer(f"🌐 **Fed-Banned User Blocked:** {user.full_name} (`{reason}`)", parse_mode=None)
                except Exception:
                    pass
                continue
        if s.get("antiraid"):
            try:
                await message.bot.ban_chat_member(cid, user.id)
                await message.bot.unban_chat_member(cid, user.id)
            except Exception:
                pass
            continue
        if s.get("captcha"):
            try:
                await message.bot.restrict_chat_member(cid, user.id, ChatPermissions(can_send_messages=False))
                PENDING_CAPTCHA.add((cid, user.id))
                if mode == "math":
                    a, b = random.randint(1, 9), random.randint(1, 9)
                    ans = a + b
                    opts = [ans, ans + random.randint(1, 3), max(1, ans - random.randint(1, 3))]
                    random.shuffle(opts)
                    btns = [[InlineKeyboardButton(text=str(o), callback_data=f"cap_{user.id}_{1 if o == ans else 0}") for o in opts]]
                    txt = f"🛡️ **Math Verification!**\n{user.full_name}, solve **{a} + {b} = ?** within 2 mins:"
                else:
                    btns = [[InlineKeyboardButton(text="✅ I'm Human!", callback_data=f"cap_{user.id}_1")]]
                    txt = f"🛡️ **Verification Required!**\n{user.full_name}, tap below within **2 minutes**:"

                cap_msg = await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode=None)
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
    parts = query.data.split("_")
    target_id, is_ok = int(parts[1]), int(parts[2])
    if query.from_user.id != target_id:
        return await query.answer("❌ Not for you!", show_alert=True)
    if not is_ok:
        return await query.answer("❌ Wrong answer! Try again.", show_alert=True)

    PENDING_CAPTCHA.discard((query.message.chat.id, target_id))
    await query.bot.restrict_chat_member(
        query.message.chat.id, target_id,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await query.message.edit_text(f"✅ {query.from_user.full_name} verified! Welcome~ 🌸", parse_mode=None)


# --- 4. Clean Service Messages ---
@router.message(F.left_chat_member | F.pinned_message | F.new_chat_title | F.new_chat_photo)
async def clean_service_msgs(message: Message):
    s = await get_chat_settings(message.chat.id)
    if s.get("cleanservice"):
        try:
            await message.delete()
        except Exception:
            pass


# --- 5. Command Disabling (/disable, /enable, /disabled) ---
@router.message(Command("disable", "enable", "disabled", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def disable_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "disabled":
        cmds = await get_disabled_cmds(message.chat.id)
        return await message.answer("🚫 **Disabled:**\n• " + "\n• ".join(cmds) if cmds else "✅ None disabled.")
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    p = message.text.split()
    if len(p) < 2:
        return await message.answer(f"Usage: `/{cmd} gacha`")
    target = p[1].lstrip("/!").lower()
    if cmd == "disable":
        await disable_cmd(message.chat.id, target); await message.answer(f"🚫 Disabled `/{target}`.")
    else:
        await enable_cmd(message.chat.id, target); await message.answer(f"✅ Enabled `/{target}`.")


# --- 6. Auto-Filters (/filter, /stop, /stopall, /filters) ---
@router.message(Command("filter", "stop", "stopall", "filters", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def filter_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "filters":
        flts = await get_filters(message.chat.id)
        return await message.answer("📝 **Filters:**\n• " + "\n• ".join(flts.keys()) if flts else "📝 No active filters.")
    if not await _is_adm(message):
        return await message.answer("❌ Admins only!")
    if cmd == "stopall":
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM chat_filters WHERE chat_id=$1", message.chat.id)
        return await message.answer("🗑️ Removed ALL filters!")
    if cmd == "filter":
        p = message.text.split(None, 2)
        if len(p) < 3:
            return await message.answer("Usage: `/filter <word> <reply>`")
        await add_filter(message.chat.id, p[1].lower(), p[2])
        await message.answer(f"✨ Filter added for `{p[1].lower()}`!")
    elif cmd == "stop":
        p = message.text.split()
        if len(p) < 2:
            return await message.answer("Usage: `/stop <word>`")
        await remove_filter(message.chat.id, p[1].lower())
        await message.answer(f"🗑️ Filter `{p[1].lower()}` removed!")
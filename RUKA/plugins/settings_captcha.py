import random, asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatJoinRequest, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA.utils.db import (
    get_pool, get_chat_settings, toggle_setting, add_filter, remove_filter, get_filters,
    disable_cmd, enable_cmd, get_disabled_cmds, get_chat_fed, is_fbanned, get_log_channel
)

router = Router()
PENDING_CAPTCHA: set[tuple[int, int]] = set()
CAPTCHA_MODES: dict[int, str] = {}
AUTO_APPROVE: set[int] = set()


async def _is_adm(m: Message, notify: bool = True) -> bool:
    if m.chat.type not in ("group", "supergroup"): return False
    if m.sender_chat and m.sender_chat.id == m.chat.id: return True
    mem = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
    if mem.status in ("creator", "administrator"): return True
    if notify: await m.answer("❌ You must be an admin to use this command!")
    return False


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
    if not await _is_adm(message): return
    s = await get_chat_settings(message.chat.id)
    await message.answer(f"⚙️ {message.chat.title} — Security & Settings", reply_markup=_settings_markup(s), parse_mode=None)


@router.callback_query(F.data.startswith("set_"))
async def settings_callbacks(query: CallbackQuery):
    action = query.data.split("_")[1]
    if action == "close": return await query.message.delete()
    mem = await query.bot.get_chat_member(query.message.chat.id, query.from_user.id)
    if mem.status not in ("creator", "administrator"): return await query.answer("❌ Admins only!", show_alert=True)
    new_val = await toggle_setting(query.message.chat.id, action)
    s = await get_chat_settings(query.message.chat.id)
    await query.message.edit_reply_markup(reply_markup=_settings_markup(s))
    await query.answer(f"{action.capitalize()} -> {'ON ✅' if new_val else 'OFF ❌'}")
    if lid := await get_log_channel(query.message.chat.id):
        try: await query.bot.send_message(lid, f"⚙️ {action} -> {'ON' if new_val else 'OFF'} in {query.message.chat.title} by {query.from_user.full_name}", parse_mode=None)
        except Exception: pass


# --- 2. Quick Toggles, CAPTCHA Mode & Join Requests ---
@router.message(Command("captcha", "antiraid", "cleanservice", "cleancommand", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def quick_toggle_cmd(message: Message):
    if not await _is_adm(message): return
    cmd = message.text.split()[0].lstrip("/!").split("@")[0].lower()
    new_val = await toggle_setting(message.chat.id, cmd)
    await message.answer(f"🛡️ **{cmd.capitalize()}** is now **{'ON ✅' if new_val else 'OFF ❌'}**!")


@router.message(Command("captchamode", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def captchamode_cmd(message: Message):
    if not await _is_adm(message): return
    p = message.text.split()
    if len(p) > 1 and p[1].lower() in ("button", "math"):
        CAPTCHA_MODES[message.chat.id] = p[1].lower()
        return await message.answer(f"🛡️ CAPTCHA mode set to **{p[1].lower()}**!")
    await message.answer("Usage: `/captchamode button` or `/captchamode math`")


@router.message(Command("autoapprove", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def autoapprove_cmd(message: Message):
    if not await _is_adm(message): return
    p = message.text.split()
    if len(p) > 1 and p[1].lower() in ("off", "no"):
        AUTO_APPROVE.discard(message.chat.id); return await message.answer("🚪 Join Request Auto-Approve: **OFF ❌**")
    AUTO_APPROVE.add(message.chat.id); await message.answer("🚪 Join Request Auto-Approve: **ON ✅**")


@router.chat_join_request()
async def handle_join_req(req: ChatJoinRequest):
    cid = req.chat.id
    if fed_id := await get_chat_fed(cid):
        if await is_fbanned(fed_id, req.from_user.id): return await req.decline()
    if cid in AUTO_APPROVE: await req.approve()


# --- 3. Forum Topic Management ---
@router.message(Command("newtopic", "closetopic", "reopentopic", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def topic_cmds(message: Message):
    if not await _is_adm(message): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    try:
        if cmd == "newtopic":
            p = message.text.split(None, 1)
            if len(p) < 2: return await message.answer("Usage: `/newtopic <Topic Name>`")
            t = await message.bot.create_forum_topic(message.chat.id, name=p[1][:128])
            return await message.answer(f"🧵 Created topic **{t.name}**!")
        if not message.message_thread_id: return await message.answer("❌ Run this inside a Forum Topic!")
        if cmd == "closetopic": await message.bot.close_forum_topic(message.chat.id, message.message_thread_id); await message.answer("🔒 Topic closed!")
        else: await message.bot.reopen_forum_topic(message.chat.id, message.message_thread_id); await message.answer("🔓 Topic reopened!")
    except Exception as e:
        await message.answer(f"❌ Topic action failed: {e}", parse_mode=None)


# --- 4. Join Handler: Fed-Ban + Anti-Raid + Button/Math CAPTCHA ---
@router.message(F.new_chat_members)
async def on_user_join(message: Message):
    cid = message.chat.id
    s = await get_chat_settings(cid)
    if s.get("cleanservice"):
        try: await message.delete()
        except Exception: pass
    fed_id, mode = await get_chat_fed(cid), CAPTCHA_MODES.get(cid, "button")
    for user in message.new_chat_members:
        if user.is_bot: continue
        if fed_id and (reason := await is_fbanned(fed_id, user.id)):
            try:
                await message.bot.ban_chat_member(cid, user.id)
                await message.answer(f"🌐 Fed-Banned User Blocked: {user.full_name} ({reason})", parse_mode=None)
            except Exception: pass
            continue
        if s.get("antiraid"):
            try: await message.bot.ban_chat_member(cid, user.id); await message.bot.unban_chat_member(cid, user.id)
            except Exception: pass
            continue
        if s.get("captcha"):
            try:
                await message.bot.restrict_chat_member(cid, user.id, ChatPermissions(can_send_messages=False))
                PENDING_CAPTCHA.add((cid, user.id))
                if mode == "math":
                    a, b = random.randint(1, 9), random.randint(1, 9); ans = a + b
                    opts = [ans, ans + random.randint(1, 3), max(1, ans - random.randint(1, 3))]; random.shuffle(opts)
                    btns = [[InlineKeyboardButton(text=str(o), callback_data=f"cap_{user.id}_{1 if o == ans else 0}") for o in opts]]
                    txt = f"🛡️ Math Verification: {user.full_name}, solve {a} + {b} = ? within 2 mins:"
                else:
                    btns = [[InlineKeyboardButton(text="✅ I'm Human!", callback_data=f"cap_{user.id}_1")]]
                    txt = f"🛡️ Verification Required: {user.full_name}, tap below within 2 mins:"
                cap_msg = await message.answer(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode=None)
                asyncio.create_task(_captcha_timeout(message.bot, cid, user.id, cap_msg.message_id))
            except Exception: pass


async def _captcha_timeout(bot, cid: int, uid: int, msg_id: int):
    await asyncio.sleep(120)
    if (cid, uid) in PENDING_CAPTCHA:
        PENDING_CAPTCHA.discard((cid, uid))
        try: await bot.ban_chat_member(cid, uid); await bot.unban_chat_member(cid, uid); await bot.delete_message(cid, msg_id)
        except Exception: pass


@router.callback_query(F.data.startswith("cap_"))
async def captcha_verify(query: CallbackQuery):
    _, tid, ok = query.data.split("_"); tid, ok = int(tid), int(ok)
    if query.from_user.id != tid: return await query.answer("❌ Not for you!", show_alert=True)
    if not ok: return await query.answer("❌ Wrong answer!", show_alert=True)
    PENDING_CAPTCHA.discard((query.message.chat.id, tid))
    await query.bot.restrict_chat_member(query.message.chat.id, tid, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
    await query.message.edit_text(f"✅ {query.from_user.full_name} verified! Welcome~ 🌸", parse_mode=None)


@router.message(F.left_chat_member | F.pinned_message | F.new_chat_title | F.new_chat_photo)
async def clean_service_msgs(message: Message):
    if (await get_chat_settings(message.chat.id)).get("cleanservice"):
        try: await message.delete()
        except Exception: pass


@router.message(Command("disable", "enable", "disabled", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def disable_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "disabled":
        cmds = await get_disabled_cmds(message.chat.id)
        return await message.answer("🚫 **Disabled:**\n• " + "\n• ".join(cmds) if cmds else "✅ None disabled.")
    if not await _is_adm(message): return
    p = message.text.split()
    if len(p) < 2: return await message.answer(f"Usage: `/{cmd} gacha`")
    tgt = p[1].lstrip("/!").lower()
    if cmd == "disable": await disable_cmd(message.chat.id, tgt); await message.answer(f"🚫 Disabled `/{tgt}`.")
    else: await enable_cmd(message.chat.id, tgt); await message.answer(f"✅ Enabled `/{tgt}`.")


@router.message(Command("filter", "stop", "stopall", "filters", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def filter_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "filters":
        flts = await get_filters(message.chat.id)
        return await message.answer("📝 **Filters:**\n• " + "\n• ".join(flts.keys()) if flts else "📝 No active filters.")
    if not await _is_adm(message): return
    if cmd == "stopall":
        pool = await get_pool()
        async with pool.acquire() as conn: await conn.execute("DELETE FROM chat_filters WHERE chat_id=$1", message.chat.id)
        return await message.answer("🗑️ Removed ALL filters!")
    if cmd == "filter":
        p = message.text.split(None, 2)
        if len(p) < 3: return await message.answer("Usage: `/filter <word> <reply>`")
        await add_filter(message.chat.id, p[1].lower(), p[2]); await message.answer(f"✨ Filter added for `{p[1].lower()}`!")
    elif cmd == "stop":
        p = message.text.split()
        if len(p) < 2: return await message.answer("Usage: `/stop <word>`")
        await remove_filter(message.chat.id, p[1].lower()); await message.answer(f"🗑️ Filter `{p[1].lower()}` removed!")
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


async def is_admin(message: Message, right: str = None) -> bool:
    if message.chat.type not in ("group", "supergroup"): return False
    if message.sender_chat and message.sender_chat.id == message.chat.id: return True
    m = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if m.status == "creator": return True
    if m.status != "administrator":
        await message.answer("❌ You must be an admin to use this command!"); return False
    if right and not getattr(m, right, False):
        await message.answer(f"❌ You are missing the `{right}` permission!"); return False
    return True


def parse_time(s: str) -> datetime | None:
    if len(s) < 2 or not s[:-1].isdigit(): return None
    u, v = s[-1].lower(), int(s[:-1])
    return datetime.now() + (timedelta(minutes=v) if u == "m" else timedelta(hours=v) if u == "h" else timedelta(days=v) if u == "d" else timedelta(0)) if u in ("m", "h", "d") else None


def get_tid(message: Message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user: return message.reply_to_message.from_user.id
    p = message.text.split()
    return int(p[1]) if len(p) > 1 and p[1].lstrip("-").isdigit() else None


def _err(e: Exception) -> str:
    t = str(e)
    if "CHAT_ADMIN_REQUIRED" in t or "RIGHT_FORBIDDEN" in t: return "❌ I lack admin rights for that (or they weren't promoted by me)!"
    if "USER_ADMIN_INVALID" in t or "owner" in t.lower(): return "❌ I can't do that to another admin or the group owner!"
    return f"❌ Failed: `{t.split(':')[-1].strip()}`"


@router.message(Command("adminpanel", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def admin_panel(message: Message):
    if not await is_admin(message): return
    btns = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Ban/Mute Guide", callback_data="adm_guide"), InlineKeyboardButton(text="🔗 Invite Link", callback_data="adm_invite")],
        [InlineKeyboardButton(text="📌 Unpin All", callback_data="adm_unpinall"), InlineKeyboardButton(text="❌ Close", callback_data="adm_close")],
    ])
    await message.answer("💓 **Ruka's Admin Control Panel**\n\nChoose an action below:", reply_markup=btns)


@router.message(Command("ban", "unban", "tban", "dban", "sban", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def ban_cmds(message: Message):
    if not await is_admin(message, "can_restrict_members"): return
    cmd, tid = message.text.split()[0].lstrip("/!").lower(), get_tid(message)
    if cmd == "sban":
        try: await message.delete()
        except Exception: pass
        if tid:
            try: await message.bot.ban_chat_member(message.chat.id, tid)
            except Exception: pass
        return
    if cmd == "dban":
        if not message.reply_to_message: return await message.answer("Reply to delete & ban!")
        tid = message.reply_to_message.from_user.id
        try: await message.reply_to_message.delete()
        except Exception: pass
    if not tid: return await message.answer(f"Reply or pass User ID for `/{cmd}`!")
    try:
        if cmd == "unban": await message.bot.unban_chat_member(message.chat.id, tid); return await message.answer(f"🌸 Unbanned `{tid}`!")
        if cmd == "tban":
            p = message.text.split(); until = parse_time(p[-1]) if len(p) > 1 else None
            if not until: return await message.answer("Usage: `/tban 1h` (reply)")
            await message.bot.ban_chat_member(message.chat.id, tid, until_date=until); return await message.answer(f"⏳ **Temp-Banned** `{tid}` for `{p[-1]}`!")
        await message.bot.ban_chat_member(message.chat.id, tid)
        await message.answer(f"💢 **Banned** `{tid}`!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Unban", callback_data=f"unban_{tid}")]]))
    except Exception as e: await message.answer(_err(e))


@router.message(Command("kick", "dkick", "skick", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def kick_cmds(message: Message):
    if not await is_admin(message, "can_restrict_members"): return
    cmd, tid = message.text.split()[0].lstrip("/!").lower(), get_tid(message)
    if not tid: return await message.answer("Reply or pass User ID to kick!")
    try:
        if cmd == "dkick" and message.reply_to_message: await message.reply_to_message.delete()
        elif cmd == "skick": await message.delete()
        await message.bot.ban_chat_member(message.chat.id, tid); await message.bot.unban_chat_member(message.chat.id, tid)
        if cmd != "skick": await message.answer(f"👢 **Kicked** `{tid}`!")
    except Exception as e:
        if cmd != "skick": await message.answer(_err(e))


@router.message(Command("mute", "unmute", "tmute", "dmute", "smute", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def mute_cmds(message: Message):
    if not await is_admin(message, "can_restrict_members"): return
    cmd, tid = message.text.split()[0].lstrip("/!").lower(), get_tid(message)
    if cmd == "smute":
        try: await message.delete()
        except Exception: pass
        if tid:
            try: await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False))
            except Exception: pass
        return
    if cmd == "dmute" and message.reply_to_message:
        tid = message.reply_to_message.from_user.id
        try: await message.reply_to_message.delete()
        except Exception: pass
    if not tid: return await message.answer(f"Reply or pass User ID for `/{cmd}`!")
    try:
        if cmd == "unmute":
            await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
            return await message.answer(f"🔊 `{tid}` can talk again!")
        if cmd == "tmute":
            p = message.text.split(); until = parse_time(p[-1]) if len(p) > 1 else None
            if not until: return await message.answer("Usage: `/tmute 30m` (reply)")
            await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False), until_date=until)
            return await message.answer(f"🤐 **Temp-Muted** `{tid}` for `{p[-1]}`!")
        await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False))
        await message.answer(f"🤫 **Muted** `{tid}`!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔊 Unmute", callback_data=f"unmute_{tid}")]]))
    except Exception as e: await message.answer(_err(e))


@router.message(Command("purge", "spurge", "del", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def purge_cmds(message: Message):
    if not await is_admin(message, "can_delete_messages"): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "del":
        try:
            if message.reply_to_message: await message.reply_to_message.delete()
            await message.delete()
        except Exception as e: await message.answer(_err(e))
        return
    if not message.reply_to_message: return await message.answer("Reply to start purging!")
    ids = list(range(message.reply_to_message.message_id, message.message_id + 1))
    try:
        await message.bot.delete_messages(message.chat.id, ids)
        if cmd == "purge":
            done = await message.answer(f"✨ Purged **{len(ids)}** messages!")
            await asyncio.sleep(2); await done.delete()
    except Exception as e: await message.answer(_err(e))


@router.message(Command("pin", "unpin", "unpinall", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def pin_cmds(message: Message):
    if not await is_admin(message, "can_pin_messages"): return
    cmd = message.text.split()[0].lstrip("/!").lower()
    try:
        if cmd == "unpinall": await message.bot.unpin_all_chat_messages(message.chat.id); return await message.answer("📌 All unpinned!")
        if cmd == "unpin":
            if message.reply_to_message: await message.bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
            else: await message.bot.unpin_chat_message(message.chat.id)
            return await message.answer("📌 Unpinned!")
        if not message.reply_to_message: return await message.answer("Reply to a message to pin!")
        await message.bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True)
        await message.answer("📌 **Pinned!**", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📌 Unpin", callback_data=f"unpin_{message.reply_to_message.message_id}")]]))
    except Exception as e: await message.answer(_err(e))


@router.message(Command("promote", "fullpromote", "demote", "settitle", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def promote_cmds(message: Message):
    if not await is_admin(message, "can_promote_members"): return
    cmd, tid = message.text.split()[0].lstrip("/!").lower(), get_tid(message)
    if not tid: return await message.answer(f"Reply or pass User ID for `/{cmd}`!")
    try:
        if cmd == "demote": await message.bot.promote_chat_member(message.chat.id, tid); return await message.answer(f"⬇️ `{tid}` demoted.")
        if cmd == "settitle":
            p = message.text.split(None, 1)
            if len(p) < 2: return await message.answer("Usage: `/settitle <title>`")
            await message.bot.set_chat_administrator_custom_title(message.chat.id, tid, p[1][:16])
            return await message.answer(f"🏷️ Set title to **{p[1][:16]}**!")
        full = cmd == "fullpromote"
        await message.bot.promote_chat_member(message.chat.id, tid, can_manage_chat=full, can_promote_members=full, can_change_info=full, can_delete_messages=True, can_restrict_members=True, can_invite_users=True, can_pin_messages=True, can_manage_video_chats=True)
        await message.answer(f"💓 **Promoted** `{tid}`!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬇️ Demote", callback_data=f"demote_{tid}")]]))
    except Exception as e: await message.answer(_err(e))


@router.message(Command("invitelink", "revokeinvite", "setgtitle", "setgdesc", "delgpic", "slowmode", "admins", prefix="/!"), F.chat.type.in_({"group", "supergroup"}))
async def group_misc_cmds(message: Message):
    cmd = message.text.split()[0].lstrip("/!").lower()
    if cmd == "admins":
        adms = await message.bot.get_chat_administrators(message.chat.id)
        return await message.answer(f"🛡️ {message.chat.title} Admins:\n\n" + "\n".join(f"{'👑' if m.status == 'creator' else '⭐'} {m.user.full_name}" for m in adms if not m.user.is_bot), parse_mode=None)
    try:
        if cmd in ("invitelink", "revokeinvite"):
            if not await is_admin(message, "can_invite_users"): return
            if cmd == "revokeinvite": return await message.answer(f"🔄 **New Link:**\n{(await message.bot.revoke_chat_invite_link(message.chat.id, await message.bot.export_chat_invite_link(message.chat.id))).invite_link}")
            return await message.answer(f"🔗 **Invite Link:**\n{await message.bot.export_chat_invite_link(message.chat.id)}")
        if cmd in ("setgtitle", "setgdesc", "delgpic"):
            if not await is_admin(message, "can_change_info"): return
            if cmd == "delgpic": await message.bot.delete_chat_photo(message.chat.id); return await message.answer("🗑️ Group photo deleted!")
            p = message.text.split(None, 1)
            if len(p) < 2: return await message.answer("Provide the new text!")
            if cmd == "setgtitle": await message.bot.set_chat_title(message.chat.id, p[1]); return await message.answer(f"✨ Title: **{p[1]}**")
            await message.bot.set_chat_description(message.chat.id, p[1]); return await message.answer("📝 Description updated!")
        if cmd == "slowmode":
            if not await is_admin(message, "can_restrict_members"): return
            p = message.text.split()
            if len(p) < 2 or not p[1].isdigit(): return await message.answer("Usage: `/slowmode 10`")
            await message.bot.set_chat_slow_mode_delay(message.chat.id, int(p[1]))
            await message.answer(f"🐢 Slowmode: **{p[1]}s**" if int(p[1]) > 0 else "🐇 Slowmode OFF!")
    except Exception as e: await message.answer(_err(e))


@router.callback_query(F.data.startswith(("unban_", "unmute_", "demote_", "unpin_", "adm_")))
async def admin_callbacks(query: CallbackQuery):
    cid = query.message.chat.id
    if (await query.bot.get_chat_member(cid, query.from_user.id)).status not in ("creator", "administrator"):
        return await query.answer("❌ Admins only!", show_alert=True)
    data = query.data
    if data == "adm_close": return await query.message.delete()
    if data == "adm_guide": return await query.answer("Use /ban, /dban, /sban, /tban, /mute, /dmute, /purge, /promote, /slowmode!", show_alert=True)
    if data == "adm_invite":
        try: return await query.message.answer(f"🔗 {await query.bot.export_chat_invite_link(cid)}")
        except Exception as e: return await query.answer(_err(e), show_alert=True)
    if data == "adm_unpinall":
        try: await query.bot.unpin_all_chat_messages(cid); return await query.answer("📌 Unpinned all!", show_alert=True)
        except Exception as e: return await query.answer(_err(e), show_alert=True)
    act, tid = data.split("_"); tid = int(tid)
    try:
        if act == "unban": await query.bot.unban_chat_member(cid, tid); await query.message.edit_text("🌸 Unbanned!")
        elif act == "unmute": await query.bot.restrict_chat_member(cid, tid, ChatPermissions(can_send_messages=True)); await query.message.edit_text("🔊 Unmuted!")
        elif act == "demote": await query.bot.promote_chat_member(cid, tid); await query.message.edit_text("⬇️ Demoted!")
        elif act == "unpin": await query.bot.unpin_chat_message(cid, tid); await query.message.edit_text("📌 Unpinned!")
    except Exception as e: await query.answer(_err(e), show_alert=True)
    await query.answer()
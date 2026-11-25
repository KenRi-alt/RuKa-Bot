import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

router = Router()


async def is_admin(message: Message, right: str = None) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return False
    member = await message.bot.get_chat_member(message.chat.id, message.from_user.id)
    if member.status == "creator":
        return True
    if member.status != "administrator":
        await message.answer("❌ You must be an admin to use this command!")
        return False
    if right and not getattr(member, right, False):
        await message.answer(f"❌ You are missing the `{right}` permission!")
        return False
    return True


def parse_time(time_str: str) -> datetime | None:
    if len(time_str) < 2 or not time_str[:-1].isdigit():
        return None
    unit, val = time_str[-1].lower(), int(time_str[:-1])
    if unit == "m":
        return datetime.now() + timedelta(minutes=val)
    if unit == "h":
        return datetime.now() + timedelta(hours=val)
    if unit == "d":
        return datetime.now() + timedelta(days=val)
    return None


def get_target_id(message: Message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lstrip("-").isdigit():
        return int(parts[1])
    return None


# 1. /adminpanel
@router.message(Command("adminpanel"), F.chat.type.in_({"group", "supergroup"}))
async def admin_panel(message: Message):
    if not await is_admin(message):
        return
    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔨 Ban/Mute Guide", callback_data="adm_guide"),
            InlineKeyboardButton(text="🔗 Invite Link", callback_data="adm_invite"),
        ],
        [
            InlineKeyboardButton(text="📌 Unpin All", callback_data="adm_unpinall"),
            InlineKeyboardButton(text="❌ Close", callback_data="adm_close"),
        ]
    ])
    await message.answer(
        "💓 **Ruka's Admin Control Panel**\n\n"
        "Hmph! I'm keeping a close eye on this group for you~\nChoose an action below:",
        reply_markup=buttons
    )


# 2–6: /ban, /unban, /tban, /dban, /sban
@router.message(Command("ban"), F.chat.type.in_({"group", "supergroup"}))
async def ban_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to someone or pass their User ID to ban!")
    await message.bot.ban_chat_member(message.chat.id, tid)
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔓 Unban", callback_data=f"unban_{tid}")]])
    await message.answer(f"💢 **Banned** `{tid}`! Nobody messes with my group!", reply_markup=btn)


@router.message(Command("unban"), F.chat.type.in_({"group", "supergroup"}))
async def unban_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply or pass User ID to unban!")
    await message.bot.unban_chat_member(message.chat.id, tid)
    await message.answer(f"🌸 Fine~ I unbanned `{tid}`. Better behave!")


@router.message(Command("tban"), F.chat.type.in_({"group", "supergroup"}))
async def tban_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    parts = message.text.split()
    if not tid or len(parts) < 2:
        return await message.answer("Usage: `/tban 1h` (reply)")
    until = parse_time(parts[-1])
    if not until:
        return await message.answer("Invalid time! Use `10m`, `2h`, or `1d`.")
    await message.bot.ban_chat_member(message.chat.id, tid, until_date=until)
    await message.answer(f"⏳ **Temp-Banned** `{tid}` for `{parts[-1]}`!")


@router.message(Command("dban"), F.chat.type.in_({"group", "supergroup"}))
async def dban_user(message: Message):
    if not await is_admin(message, "can_restrict_members") or not message.reply_to_message:
        return
    tid = message.reply_to_message.from_user.id
    await message.reply_to_message.delete()
    await message.bot.ban_chat_member(message.chat.id, tid)
    await message.answer(f"💢 Deleted message & **Banned** `{tid}`!")


@router.message(Command("sban"), F.chat.type.in_({"group", "supergroup"}))
async def sban_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    await message.delete()
    if tid:
        await message.bot.ban_chat_member(message.chat.id, tid)


# 7–9: /kick, /dkick, /skick
@router.message(Command("kick"), F.chat.type.in_({"group", "supergroup"}))
async def kick_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to someone to kick them!")
    await message.bot.ban_chat_member(message.chat.id, tid)
    await message.bot.unban_chat_member(message.chat.id, tid)
    await message.answer(f"👢 **Kicked** `{tid}`!")


@router.message(Command("dkick"), F.chat.type.in_({"group", "supergroup"}))
async def dkick_user(message: Message):
    if not await is_admin(message, "can_restrict_members") or not message.reply_to_message:
        return
    tid = message.reply_to_message.from_user.id
    await message.reply_to_message.delete()
    await message.bot.ban_chat_member(message.chat.id, tid)
    await message.bot.unban_chat_member(message.chat.id, tid)
    await message.answer(f"👢 Deleted message & **Kicked** `{tid}`!")


@router.message(Command("skick"), F.chat.type.in_({"group", "supergroup"}))
async def skick_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    await message.delete()
    if tid:
        await message.bot.ban_chat_member(message.chat.id, tid)
        await message.bot.unban_chat_member(message.chat.id, tid)


# 10–14: /mute, /unmute, /tmute, /dmute, /smute
@router.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def mute_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to someone to mute them!")
    await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False))
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔊 Unmute", callback_data=f"unmute_{tid}")]])
    await message.answer(f"🤫 **Shh!** `{tid}` is muted!", reply_markup=btn)


@router.message(Command("unmute"), F.chat.type.in_({"group", "supergroup"}))
async def unmute_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to someone to unmute them!")
    await message.bot.restrict_chat_member(
        message.chat.id, tid,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await message.answer(f"🔊 `{tid}` can talk again!")


@router.message(Command("tmute"), F.chat.type.in_({"group", "supergroup"}))
async def tmute_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    parts = message.text.split()
    if not tid or len(parts) < 2:
        return await message.answer("Usage: `/tmute 30m` (reply)")
    until = parse_time(parts[-1])
    if not until:
        return await message.answer("Invalid time! Use `10m`, `2h`, or `1d`.")
    await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False), until_date=until)
    await message.answer(f"🤐 **Temp-Muted** `{tid}` for `{parts[-1]}`!")


@router.message(Command("dmute"), F.chat.type.in_({"group", "supergroup"}))
async def dmute_user(message: Message):
    if not await is_admin(message, "can_restrict_members") or not message.reply_to_message:
        return
    tid = message.reply_to_message.from_user.id
    await message.reply_to_message.delete()
    await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False))
    await message.answer(f"🤫 Deleted message & **Muted** `{tid}`!")


@router.message(Command("smute"), F.chat.type.in_({"group", "supergroup"}))
async def smute_user(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    tid = get_target_id(message)
    await message.delete()
    if tid:
        await message.bot.restrict_chat_member(message.chat.id, tid, ChatPermissions(can_send_messages=False))


# 15–16: /purge, /del
@router.message(Command("purge"), F.chat.type.in_({"group", "supergroup"}))
async def purge_msgs(message: Message):
    if not await is_admin(message, "can_delete_messages") or not message.reply_to_message:
        return
    msg_ids = list(range(message.reply_to_message.message_id, message.message_id + 1))
    await message.bot.delete_messages(message.chat.id, msg_ids)
    done = await message.answer(f"✨ Purged **{len(msg_ids)}** messages!")
    await asyncio.sleep(2)
    await done.delete()


@router.message(Command("del"), F.chat.type.in_({"group", "supergroup"}))
async def del_msg(message: Message):
    if not await is_admin(message, "can_delete_messages"):
        return
    if message.reply_to_message:
        await message.reply_to_message.delete()
    await message.delete()


# 17–19: /pin, /unpin, /unpinall
@router.message(Command("pin"), F.chat.type.in_({"group", "supergroup"}))
async def pin_msg(message: Message):
    if not await is_admin(message, "can_pin_messages") or not message.reply_to_message:
        return
    await message.bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id, disable_notification=True)
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📌 Unpin", callback_data=f"unpin_{message.reply_to_message.message_id}")]])
    await message.answer("📌 **Pinned!**", reply_markup=btn)


@router.message(Command("unpin"), F.chat.type.in_({"group", "supergroup"}))
async def unpin_msg(message: Message):
    if not await is_admin(message, "can_pin_messages"):
        return
    if message.reply_to_message:
        await message.bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
    else:
        await message.bot.unpin_chat_message(message.chat.id)
    await message.answer("📌 Unpinned!")


@router.message(Command("unpinall"), F.chat.type.in_({"group", "supergroup"}))
async def unpin_all_msgs(message: Message):
    if not await is_admin(message, "can_pin_messages"):
        return
    await message.bot.unpin_all_chat_messages(message.chat.id)
    await message.answer("📌 All messages unpinned!")


# 20–22: /promote, /demote, /settitle
@router.message(Command("promote"), F.chat.type.in_({"group", "supergroup"}))
async def promote_user(message: Message):
    if not await is_admin(message, "can_promote_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to someone to promote them!")
    await message.bot.promote_chat_member(
        message.chat.id, tid,
        can_delete_messages=True, can_restrict_members=True,
        can_invite_users=True, can_pin_messages=True, can_manage_video_chats=True
    )
    btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬇️ Demote", callback_data=f"demote_{tid}")]])
    await message.answer(f"💓 **Doki-doki!** `{tid}` is now an Admin!", reply_markup=btn)


@router.message(Command("demote"), F.chat.type.in_({"group", "supergroup"}))
async def demote_user(message: Message):
    if not await is_admin(message, "can_promote_members"):
        return
    tid = get_target_id(message)
    if not tid:
        return await message.answer("Reply to an admin to demote them!")
    await message.bot.promote_chat_member(message.chat.id, tid)
    await message.answer(f"⬇️ `{tid}` has been demoted.")


@router.message(Command("settitle"), F.chat.type.in_({"group", "supergroup"}))
async def set_admin_title(message: Message):
    if not await is_admin(message, "can_promote_members") or not message.reply_to_message:
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/settitle <title>` (reply)")
    await message.bot.set_chat_administrator_custom_title(message.chat.id, message.reply_to_message.from_user.id, parts[1][:16])
    await message.answer(f"🏷️ Set admin title to **{parts[1][:16]}**!")


# 23–27: /invitelink, /setgtitle, /setgdesc, /slowmode, /admins
@router.message(Command("invitelink"), F.chat.type.in_({"group", "supergroup"}))
async def get_invite(message: Message):
    if not await is_admin(message, "can_invite_users"):
        return
    link = await message.bot.export_chat_invite_link(message.chat.id)
    await message.answer(f"🔗 **Group Invite Link:**\n{link}")


@router.message(Command("setgtitle"), F.chat.type.in_({"group", "supergroup"}))
async def set_group_title(message: Message):
    if not await is_admin(message, "can_change_info"):
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Give me a new group title!")
    await message.bot.set_chat_title(message.chat.id, parts[1])
    await message.answer(f"✨ Group title changed to **{parts[1]}**!")


@router.message(Command("setgdesc"), F.chat.type.in_({"group", "supergroup"}))
async def set_group_desc(message: Message):
    if not await is_admin(message, "can_change_info"):
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Give me a new group description!")
    await message.bot.set_chat_description(message.chat.id, parts[1])
    await message.answer("📝 Group description updated!")


@router.message(Command("slowmode"), F.chat.type.in_({"group", "supergroup"}))
async def set_slowmode(message: Message):
    if not await is_admin(message, "can_restrict_members"):
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.answer("Usage: `/slowmode 10` (0, 10, 30, 60, 300, 900, 3600)")
    sec = int(parts[1])
    await message.bot.set_chat_slow_mode_delay(message.chat.id, sec)
    await message.answer(f"🐢 Slowmode set to **{sec}s**!" if sec > 0 else "🐇 Slowmode disabled!")


@router.message(Command("admins"), F.chat.type.in_({"group", "supergroup"}))
async def list_admins(message: Message):
    admins = await message.bot.get_chat_administrators(message.chat.id)
    lines = []
    for m in admins:
        if not m.user.is_bot:
            role = "👑" if m.status == "creator" else "⭐"
            lines.append(f"{role} {m.user.full_name}")
    await message.answer(f"🛡️ **{message.chat.title} Admins:**\n\n" + "\n".join(lines))


# --- Callback Handler ---
@router.callback_query(F.data.startswith(("unban_", "unmute_", "demote_", "unpin_", "adm_")))
async def admin_callbacks(query: CallbackQuery):
    data, chat_id = query.data, query.message.chat.id

    if data == "adm_close":
        return await query.message.delete()
    if data == "adm_guide":
        return await query.answer("Use /ban, /dban, /sban, /tban, /mute, /dmute, /purge, /promote, /slowmode!", show_alert=True)
    if data == "adm_invite":
        link = await query.bot.export_chat_invite_link(chat_id)
        return await query.message.answer(f"🔗 {link}")
    if data == "adm_unpinall":
        await query.bot.unpin_all_chat_messages(chat_id)
        return await query.answer("📌 All messages unpinned!", show_alert=True)

    action, target_id = data.split("_")
    target_id = int(target_id)
    if action == "unban":
        await query.bot.unban_chat_member(chat_id, target_id)
        await query.message.edit_text("🌸 Unbanned via button!")
    elif action == "unmute":
        await query.bot.restrict_chat_member(chat_id, target_id, ChatPermissions(can_send_messages=True))
        await query.message.edit_text("🔊 Unmuted via button!")
    elif action == "demote":
        await query.bot.promote_chat_member(chat_id, target_id)
        await query.message.edit_text("⬇️ Demoted via button!")
    elif action == "unpin":
        await query.bot.unpin_chat_message(chat_id, target_id)
        await query.message.edit_text("📌 Unpinned via button!")
    await query.answer()
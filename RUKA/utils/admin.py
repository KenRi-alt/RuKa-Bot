import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    ChatPermissions,
    ChatPrivileges,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from RUKA import CONFIG
from ..utils import admin, botAdmin, groupOnly, chatAction


# --- Helper: Parse Target User (Reply or @username / ID) ---
async def get_target(client, message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        arg = message.command[1]
        try:
            return await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception:
            return None
    return None


# --- Helper: Parse Time (e.g. 10m, 2h, 1d) ---
def parse_time(time_str: str) -> datetime | None:
    unit = time_str[-1].lower()
    if not time_str[:-1].isdigit():
        return None
    val = int(time_str[:-1])
    if unit == "m":
        return datetime.now() + timedelta(minutes=val)
    if unit == "h":
        return datetime.now() + timedelta(hours=val)
    if unit == "d":
        return datetime.now() + timedelta(days=val)
    return None


# 1. /adminpanel — Interactive Control Center
@Client.on_message(filters.command("adminpanel") & filters.group)
@groupOnly()
@admin(msg=True)
async def admin_panel(client, message):
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔨 Ban/Mute Guide", callback_data="adm_guide"),
            InlineKeyboardButton("🧹 Clean Zombies", callback_data="adm_zombies"),
        ],
        [
            InlineKeyboardButton("🔗 Invite Link", callback_data="adm_invite"),
            InlineKeyboardButton("📌 Unpin All", callback_data="adm_unpinall"),
        ],
        [
            InlineKeyboardButton("❌ Close Menu", callback_data="adm_close")
        ]
    ])
    await message.reply_text(
        "💓 **Ruka's Admin Control Panel**\n\n"
        "Hmph! I'm keeping a close eye on this group for you~\n"
        "Choose an action below, okay?",
        reply_markup=buttons
    )


# 2. /ban
@Client.on_message(filters.command("ban") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
@chatAction(action="typing")
async def ban_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Eh?! Reply to someone or give me their `@username` / ID to ban!")
    await client.ban_chat_member(message.chat.id, target.id)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔓 Unban", callback_data=f"unban_{target.id}")]])
    await message.reply_text(
        f"💢 **Banned!**\n{target.mention} has been kicked out of my group! Nobody messes with us!",
        reply_markup=btn
    )


# 3. /unban
@Client.on_message(filters.command("unban") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def unban_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Tell me who to unban! Reply or pass their ID.")
    await client.unban_chat_member(message.chat.id, target.id)
    await message.reply_text(f"🌸 Fine~ I unbanned {target.mention}. Better behave this time!")


# 4. /tban (Timed Ban)
@Client.on_message(filters.command("tban") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def tban_user(client, message):
    target = await get_target(client, message)
    if not target or len(message.command) < 2:
        return await message.reply_text("Usage: `/tban 1h` (reply) or `/tban @user 1d`")
    time_arg = message.command[-1]
    until = parse_time(time_arg)
    if not until:
        return await message.reply_text("Invalid time! Use `10m`, `2h`, or `1d`.")
    await client.ban_chat_member(message.chat.id, target.id, until_date=until)
    await message.reply_text(f"⏳ **Temp-Banned** {target.mention} for `{time_arg}`! Go cool off!")


# 5. /kick
@Client.on_message(filters.command("kick") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def kick_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Who am I kicking? Reply to them!")
    await client.ban_chat_member(message.chat.id, target.id)
    await client.unban_chat_member(message.chat.id, target.id)
    await message.reply_text(f"👢 **Kicked** {target.mention}! Don't come back unless you're nice~")


# 6. /mute
@Client.on_message(filters.command("mute") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def mute_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Reply to someone to mute them!")
    await client.restrict_chat_member(message.chat.id, target.id, ChatPermissions())
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔊 Unmute", callback_data=f"unmute_{target.id}")]])
    await message.reply_text(f"🤫 **Shh!** {target.mention} is muted! Listen to Ruka instead~", reply_markup=btn)


# 7. /unmute
@Client.on_message(filters.command("unmute") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def unmute_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Reply to someone to unmute them!")
    await client.restrict_chat_member(
        message.chat.id, target.id,
        ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
    )
    await message.reply_text(f"🔊 Okay, {target.mention} can talk again!")


# 8. /tmute (Timed Mute)
@Client.on_message(filters.command("tmute") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def tmute_user(client, message):
    target = await get_target(client, message)
    if not target or len(message.command) < 2:
        return await message.reply_text("Usage: `/tmute 30m` (reply) or `/tmute @user 2h`")
    time_arg = message.command[-1]
    until = parse_time(time_arg)
    if not until:
        return await message.reply_text("Invalid time! Use `10m`, `2h`, or `1d`.")
    await client.restrict_chat_member(message.chat.id, target.id, ChatPermissions(), until_date=until)
    await message.reply_text(f"🤐 **Temp-Muted** {target.mention} for `{time_arg}`!")


# 9. /purge
@Client.on_message(filters.command("purge") & filters.group)
@groupOnly()
@admin(rights=["can_delete_messages"], msg=True)
@botAdmin(rights=["can_delete_messages"], msg=True)
async def purge_msgs(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to the message where I should start purging!")
    msg_ids = list(range(message.reply_to_message.id, message.id + 1))
    await client.delete_messages(message.chat.id, msg_ids)
    done = await message.reply_text(f"✨ Purged **{len(msg_ids)}** messages! Everything is spotless~")
    time.sleep(2)
    await done.delete()


# 10. /del
@Client.on_message(filters.command("del") & filters.group)
@groupOnly()
@admin(rights=["can_delete_messages"], msg=True)
@botAdmin(rights=["can_delete_messages"], msg=True)
async def del_msg(client, message):
    if message.reply_to_message:
        await message.reply_to_message.delete()
    await message.delete()


# 11. /pin
@Client.on_message(filters.command("pin") & filters.group)
@groupOnly()
@admin(rights=["can_pin_messages"], msg=True)
@botAdmin(rights=["can_pin_messages"], msg=True)
async def pin_msg(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to pin it!")
    await message.reply_to_message.pin(disable_notification=True)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("📌 Unpin", callback_data=f"unpin_{message.reply_to_message.id}")]])
    await message.reply_text("📌 **Pinned!** Everyone pay attention to this!", reply_markup=btn)


# 12. /unpin
@Client.on_message(filters.command("unpin") & filters.group)
@groupOnly()
@admin(rights=["can_pin_messages"], msg=True)
@botAdmin(rights=["can_pin_messages"], msg=True)
async def unpin_msg(client, message):
    if message.reply_to_message:
        await message.reply_to_message.unpin()
    else:
        await client.unpin_chat_message(message.chat.id)
    await message.reply_text("📌 Unpinned!")


# 13. /promote
@Client.on_message(filters.command("promote") & filters.group)
@groupOnly()
@admin(rights=["can_promote_members"], msg=True)
@botAdmin(rights=["can_promote_members"], msg=True)
async def promote_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Reply to someone to promote them!")
    await client.promote_chat_member(
        message.chat.id, target.id,
        privileges=ChatPrivileges(
            can_delete_messages=True, can_restrict_members=True,
            can_invite_users=True, can_pin_messages=True, can_manage_video_chats=True
        )
    )
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Demote", callback_data=f"demote_{target.id}")]])
    await message.reply_text(f"💓 **Doki-doki!** {target.mention} is now an Admin! Work hard!", reply_markup=btn)


# 14. /demote
@Client.on_message(filters.command("demote") & filters.group)
@groupOnly()
@admin(rights=["can_promote_members"], msg=True)
@botAdmin(rights=["can_promote_members"], msg=True)
async def demote_user(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Reply to an admin to demote them!")
    await client.promote_chat_member(message.chat.id, target.id, privileges=ChatPrivileges())
    await message.reply_text(f"⬇️ {target.mention} has been demoted back to a normal member.")


# 15. /settitle
@Client.on_message(filters.command("settitle") & filters.group)
@groupOnly()
@admin(rights=["can_promote_members"], msg=True)
@botAdmin(rights=["can_promote_members"], msg=True)
async def set_admin_title(client, message):
    if not message.reply_to_message or len(message.command) < 2:
        return await message.reply_text("Reply to an admin with `/settitle <title>`")
    title = message.text.split(None, 1)[1][:16]
    await client.set_administrator_title(message.chat.id, message.reply_to_message.from_user.id, title)
    await message.reply_text(f"🏷️ Set admin title to **{title}**!")


# 16. /invitelink
@Client.on_message(filters.command("invitelink") & filters.group)
@groupOnly()
@admin(rights=["can_invite_users"], msg=True)
@botAdmin(rights=["can_invite_users"], msg=True)
async def get_invite(client, message):
    link = await client.export_chat_invite_link(message.chat.id)
    await message.reply_text(f"🔗 **Group Invite Link:**\n{link}")


# 17. /setgtitle
@Client.on_message(filters.command("setgtitle") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
@botAdmin(rights=["can_change_info"], msg=True)
async def set_group_title(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Give me a new group title!")
    new_title = message.text.split(None, 1)[1]
    await client.set_chat_title(message.chat.id, new_title)
    await message.reply_text(f"✨ Group title changed to **{new_title}**!")


# 18. /setgdesc
@Client.on_message(filters.command("setgdesc") & filters.group)
@groupOnly()
@admin(rights=["can_change_info"], msg=True)
@botAdmin(rights=["can_change_info"], msg=True)
async def set_group_desc(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Give me a new group description!")
    new_desc = message.text.split(None, 1)[1]
    await client.set_chat_description(message.chat.id, new_desc)
    await message.reply_text("📝 Group description updated!")


# 19. /zombies (Clean Deleted Accounts)
@Client.on_message(filters.command("zombies") & filters.group)
@groupOnly()
@admin(rights=["can_restrict_members"], msg=True)
@botAdmin(rights=["can_restrict_members"], msg=True)
async def clean_zombies(client, message):
    deleted = 0
    async for m in client.get_chat_members(message.chat.id):
        if m.user.is_deleted:
            try:
                await client.ban_chat_member(message.chat.id, m.user.id)
                await client.unban_chat_member(message.chat.id, m.user.id)
                deleted += 1
            except Exception:
                pass
    await message.reply_text(f"🧟 Cleaned **{deleted}** deleted accounts! No ghosts allowed in my group~")


# 20. /gban (Owner Only)
@Client.on_message(filters.command("gban") & filters.user(CONFIG.OWNER_LIST))
async def global_ban(client, message):
    target = await get_target(client, message)
    if not target:
        return await message.reply_text("Reply or give a user ID to **Global Ban**!")
    if CONFIG.GBAN_LOGS:
        await client.send_message(CONFIG.GBAN_LOGS, f"🚨 **Global Ban**\nUser: {target.mention} (`{target.id}`)\nBy: {message.from_user.mention}")
    await message.reply_text(f"🌐 **Globally Banned** {target.mention}! Ruka's wrath knows no bounds!")


# --- Callback Handler for Inline Buttons ---
@Client.on_callback_query(filters.regex(r"^(unban_|unmute_|demote_|unpin_|adm_)"))
async def admin_callbacks(client, query):
    data = query.data
    chat_id = query.message.chat.id

    if data == "adm_close":
        return await query.message.delete()
    if data == "adm_guide":
        return await query.answer("Use /ban, /tban, /mute, /tmute, /kick, /purge, /promote, /zombies!", show_alert=True)
    if data == "adm_invite":
        link = await client.export_chat_invite_link(chat_id)
        return await query.message.reply_text(f"🔗 {link}")
    if data == "adm_unpinall":
        await client.unpin_all_chat_messages(chat_id)
        return await query.answer("📌 All messages unpinned!", show_alert=True)
    if data == "adm_zombies":
        return await query.answer("Run /zombies in chat to clean deleted accounts!", show_alert=True)

    action, target_id = data.split("_")
    target_id = int(target_id)
    if action == "unban":
        await client.unban_chat_member(chat_id, target_id)
        await query.message.edit_text("🌸 Unbanned via button!")
    elif action == "unmute":
        await client.restrict_chat_member(chat_id, target_id, ChatPermissions(can_send_messages=True))
        await query.message.edit_text("🔊 Unmuted via button!")
    elif action == "demote":
        await client.promote_chat_member(chat_id, target_id, privileges=ChatPrivileges())
        await query.message.edit_text("⬇️ Demoted via button!")
    elif action == "unpin":
        await client.unpin_chat_message(chat_id, target_id)
        await query.message.edit_text("📌 Unpinned via button!")
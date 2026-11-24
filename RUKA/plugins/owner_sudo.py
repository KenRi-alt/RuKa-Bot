import os
import sys
import time
import asyncio
import traceback
from io import StringIO
from pyrogram import Client, filters
from RUKA import CONFIG, LOGGER
from ..utils import userLevel
from ..utils.block_list import BLOCK_LIST

START_TIME = time.time()


def get_uptime() -> str:
    secs = int(time.time() - START_TIME)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h {mins}m {secs}s"


# 1. /stats — Bot Uptime & System Info
@Client.on_message(filters.command("stats"))
@userLevel("SUDO", msg=True)
async def bot_stats(client, message):
    await message.reply_text(
        f"📊 **RuKa-Bot System Stats**\n\n"
        f"⏱️ **Uptime:** `{get_uptime()}`\n"
        f"🐍 **Python:** `{sys.version.split()[0]}`\n"
        f"👑 **Owners:** `{len(CONFIG.OWNER_LIST)}`\n"
        f"🛠️ **Devs:** `{len(CONFIG.DEV_LIST)}`\n"
        f"⚡ **Sudos:** `{len(CONFIG.SUDO_LIST)}`"
    )


# 2. /sudolist — View All Privileged Users
@Client.on_message(filters.command("sudolist"))
@userLevel("SUDO", msg=True)
async def sudo_list_cmd(client, message):
    text = (
        f"👑 **RuKa-Bot Hierarchy**\n\n"
        f"**Owners:** `{CONFIG.OWNER_LIST}`\n"
        f"**Devs:** `{CONFIG.DEV_LIST}`\n"
        f"**Sudos:** `{CONFIG.SUDO_LIST}`\n"
        f"**Support:** `{CONFIG.SUPPORT_LIST}`\n"
        f"**Whitelist:** `{CONFIG.WHITE_LIST}`"
    )
    await message.reply_text(text)


# 3. /addsudo — Dynamically Add Sudo User
@Client.on_message(filters.command("addsudo"))
@userLevel("OWNER", msg=True)
async def add_sudo(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID!")
    if uid not in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.append(uid)
    await message.reply_text(f"⚡ Added `{uid}` to **SUDO_LIST**!")


# 4. /rmsudo — Remove Sudo User
@Client.on_message(filters.command("rmsudo"))
@userLevel("OWNER", msg=True)
async def rm_sudo(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID!")
    if uid in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.remove(uid)
    await message.reply_text(f"🗑️ Removed `{uid}` from **SUDO_LIST**!")


# 5. /block — Block User from Bot
@Client.on_message(filters.command("block"))
@userLevel("SUDO", msg=True)
async def block_user(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID to block!")
    if uid not in BLOCK_LIST:
        BLOCK_LIST.append(uid)
    await message.reply_text(f"🚫 Blocked `{uid}` from using Ruka!")


# 6. /unblock — Unblock User
@Client.on_message(filters.command("unblock"))
@userLevel("SUDO", msg=True)
async def unblock_user(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID to unblock!")
    if uid in BLOCK_LIST:
        BLOCK_LIST.remove(uid)
    await message.reply_text(f"✅ Unblocked `{uid}`!")


# 7. /gban — Global Ban
@Client.on_message(filters.command("gban"))
@userLevel("SUDO", msg=True)
async def gban_cmd(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID to **GBan**!")
    if CONFIG.GBAN_LOGS:
        await client.send_message(CONFIG.GBAN_LOGS, f"🌐 **GBAN**\nUser: `{uid}`\nBy: {message.from_user.mention}")
    await message.reply_text(f"🌐 **Globally Banned** `{uid}`!")


# 8. /ungban — Global Unban
@Client.on_message(filters.command("ungban"))
@userLevel("SUDO", msg=True)
async def ungban_cmd(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply to a user or pass their ID to **UnGBan**!")
    if CONFIG.GBAN_LOGS:
        await client.send_message(CONFIG.GBAN_LOGS, f"🌸 **UNGBAN**\nUser: `{uid}`\nBy: {message.from_user.mention}")
    await message.reply_text(f"🌸 **Globally Unbanned** `{uid}`!")


# 9. /gmute — Global Mute
@Client.on_message(filters.command("gmute"))
@userLevel("SUDO", msg=True)
async def gmute_cmd(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply or pass ID to **GMute**!")
    await message.reply_text(f"🔇 **Globally Muted** `{uid}`!")


# 10. /ungmute — Global Unmute
@Client.on_message(filters.command("ungmute"))
@userLevel("SUDO", msg=True)
async def ungmute_cmd(client, message):
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(message.command[1]) if len(message.command) > 1 and message.command[1].isdigit() else None)
    if not uid:
        return await message.reply_text("Reply or pass ID to **UnGMute**!")
    await message.reply_text(f"🔊 **Globally Unmuted** `{uid}`!")


# 11. /broadcast — Broadcast Message to Known Dialogs
@Client.on_message(filters.command("broadcast"))
@userLevel("OWNER", msg=True)
async def broadcast_cmd(client, message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message to broadcast it!")
    msg = await message.reply_text("📢 Broadcasting...")
    sent = 0
    async for dialog in client.get_dialogs():
        try:
            await message.reply_to_message.copy(dialog.chat.id)
            sent += 1
            await asyncio.sleep(0.3)
        except Exception:
            pass
    await msg.edit_text(f"📢 Broadcast complete! Sent to **{sent}** chats.")


# 12. /chatlist — List Active Groups
@Client.on_message(filters.command("chatlist"))
@userLevel("SUDO", msg=True)
async def chatlist_cmd(client, message):
    chats = []
    async for dialog in client.get_dialogs():
        if dialog.chat.type.name in ("GROUP", "SUPERGROUP"):
            chats.append(f"• **{dialog.chat.title}** (`{dialog.chat.id}`)")
    text = "📋 **Active Groups:**\n\n" + ("\n".join(chats[:30]) if chats else "None")
    await message.reply_text(text)


# 13. /leavechat — Make Bot Leave a Group
@Client.on_message(filters.command("leavechat"))
@userLevel("OWNER", msg=True)
async def leave_chat_cmd(client, message):
    cid = int(message.command[1]) if len(message.command) > 1 and message.command[1].lstrip("-").isdigit() else message.chat.id
    await client.leave_chat(cid)
    if cid != message.chat.id:
        await message.reply_text(f"👋 Left chat `{cid}`!")


# 14. /send — Send Message as Bot to Any Chat
@Client.on_message(filters.command("send"))
@userLevel("OWNER", msg=True)
async def send_as_bot(client, message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/send <chat_id> <text>`")
    cid = int(message.command[1])
    text = message.text.split(None, 2)[2]
    await client.send_message(cid, text)
    await message.reply_text(f"✅ Sent message to `{cid}`!")


# 15. /eval — Execute Python Code (Dev/Owner)
@Client.on_message(filters.command("eval"))
@userLevel("DEV", msg=True)
async def eval_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Give me Python code to run!")
    code = message.text.split(None, 1)[1]
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    try:
        exec(
            "async def __aexec(client, message):\n" + "\n".join(f"    {line}" for line in code.splitlines()),
            globals(),
            locals()
        )
        await locals()["__aexec"](client, message)
        out = mystdout.getvalue() or "✅ Executed (no output)."
    except Exception:
        out = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
    await message.reply_text(f"```python\n{out[:3900]}\n```")


# 16. /sh — Run Shell Command (Owner Only)
@Client.on_message(filters.command(["sh", "bash"]))
@userLevel("OWNER", msg=True)
async def shell_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/sh <command>`")
    cmd = message.text.split(None, 1)[1]
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    out = (stdout.decode() + stderr.decode()).strip() or "✅ Done."
    await message.reply_text(f"```bash\n{out[:3900]}\n```")


# 17. /logs — Send Bot Logs
@Client.on_message(filters.command("logs"))
@userLevel("DEV", msg=True)
async def logs_cmd(client, message):
    for path in ("logs.txt", "ruka.log", "bot.log"):
        if os.path.exists(path):
            return await message.reply_document(path, caption="📄 **RuKa-Bot Logs**")
    await message.reply_text("📄 No local log file found (check Render Dashboard logs).")


# 18. /restart — Restart the Bot
@Client.on_message(filters.command("restart"))
@userLevel("OWNER", msg=True)
async def restart_cmd(client, message):
    await message.reply_text("🔄 **Restarting RuKa-Bot...** See you in a few seconds! 💓")
    os.execv(sys.executable, [sys.executable] + sys.argv)
import os
import sys
import time
import asyncio
import traceback
from io import StringIO
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from RUKA import CONFIG

router = Router()
START_TIME = time.time()


def is_owner(uid: int) -> bool:
    return uid in (CONFIG.OWNER_LIST or [])


def is_sudo(uid: int) -> bool:
    return uid in (CONFIG.OWNER_LIST or []) or uid in (CONFIG.DEV_LIST or []) or uid in (CONFIG.SUDO_LIST or [])


def get_uptime() -> str:
    secs = int(time.time() - START_TIME)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h {mins}m {secs}s"


@router.message(Command("stats"))
async def bot_stats(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    await message.answer(
        f"📊 **RuKa-Bot System Stats**\n\n"
        f"⏱️ **Uptime:** `{get_uptime()}`\n"
        f"🐍 **Python:** `{sys.version.split()[0]}`\n"
        f"👑 **Owners:** `{len(CONFIG.OWNER_LIST)}`\n"
        f"⚡ **Sudos:** `{len(CONFIG.SUDO_LIST)}`"
    )


@router.message(Command("sudolist"))
async def sudo_list_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    await message.answer(
        f"👑 **RuKa-Bot Hierarchy**\n\n"
        f"**Owners:** `{CONFIG.OWNER_LIST}`\n"
        f"**Devs:** `{CONFIG.DEV_LIST}`\n"
        f"**Sudos:** `{CONFIG.SUDO_LIST}`"
    )


@router.message(Command("addsudo"))
async def add_sudo(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split()
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid not in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.append(uid)
    await message.answer(f"⚡ Added `{uid}` to **SUDO_LIST**!")


@router.message(Command("rmsudo"))
async def rm_sudo(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split()
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)
    if not uid:
        return await message.answer("Reply to a user or pass their ID!")
    if uid in CONFIG.SUDO_LIST:
        CONFIG.SUDO_LIST.remove(uid)
    await message.answer(f"🗑️ Removed `{uid}` from **SUDO_LIST**!")


@router.message(Command("gban"))
async def gban_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    parts = message.text.split()
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)
    if not uid:
        return await message.answer("Reply or pass ID to **GBan**!")
    if CONFIG.GBAN_LOGS:
        await message.bot.send_message(CONFIG.GBAN_LOGS, f"🌐 **GBAN**\nUser: `{uid}`\nBy: {message.from_user.full_name}")
    await message.answer(f"🌐 **Globally Banned** `{uid}`!")


@router.message(Command("ungban"))
async def ungban_cmd(message: Message):
    if not is_sudo(message.from_user.id):
        return await message.answer("❌ Sudo/Owner only!")
    parts = message.text.split()
    uid = message.reply_to_message.from_user.id if message.reply_to_message else (int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None)
    if not uid:
        return await message.answer("Reply or pass ID to **UnGBan**!")
    await message.answer(f"🌸 **Globally Unbanned** `{uid}`!")


@router.message(Command("send"))
async def send_as_bot(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        return await message.answer("Usage: `/send <chat_id> <text>`")
    await message.bot.send_message(int(parts[1]), parts[2])
    await message.answer(f"✅ Sent message to `{parts[1]}`!")


@router.message(Command("leavechat"))
async def leave_chat_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split()
    cid = int(parts[1]) if len(parts) > 1 and parts[1].lstrip("-").isdigit() else message.chat.id
    await message.bot.leave_chat(cid)
    if cid != message.chat.id:
        await message.answer(f"👋 Left chat `{cid}`!")


@router.message(Command("eval"))
async def eval_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Give me Python code to run!")
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()
    try:
        exec(
            "async def __aexec(message):\n" + "\n".join(f"    {line}" for line in parts[1].splitlines()),
            globals(),
            locals()
        )
        await locals()["__aexec"](message)
        out = mystdout.getvalue() or "✅ Executed (no output)."
    except Exception:
        out = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
    await message.answer(f"```python\n{out[:3900]}\n```")


@router.message(Command("sh", "bash"))
async def shell_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.answer("Usage: `/sh <command>`")
    proc = await asyncio.create_subprocess_shell(parts[1], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    out = (stdout.decode() + stderr.decode()).strip() or "✅ Done."
    await message.answer(f"```bash\n{out[:3900]}\n```")


@router.message(Command("restart"))
async def restart_cmd(message: Message):
    if not is_owner(message.from_user.id):
        return await message.answer("❌ Owner only!")
    await message.answer("🔄 **Restarting RuKa-Bot...** 💓")
    os.execv(sys.executable, [sys.executable] + sys.argv)
import os
import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from RUKA import CONFIG

router = Router()


@router.message(Command("backup"))
async def backup_postgres(message: Message):
    if message.from_user.id not in (CONFIG.OWNER_LIST or []):
        return await message.answer("❌ Owner only!")

    msg = await message.answer("⏳ Creating PostgreSQL backup...")
    backup_file = "ruka_postgres_backup.sql"

    proc = await asyncio.create_subprocess_exec(
        "pg_dump", CONFIG.DB_URL, "-f", backup_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        return await msg.edit_text(f"❌ Backup failed:\n`{stderr.decode()}`")

    doc = FSInputFile(backup_file)
    if CONFIG.LOGS_CHANNEL:
        await message.bot.send_document(CONFIG.LOGS_CHANNEL, document=doc, caption="📦 **RuKa-Bot PostgreSQL Backup**")

    for owner_id in (CONFIG.OWNER_LIST or []):
        try:
            await message.bot.send_document(owner_id, document=doc, caption="📦 **RuKa-Bot PostgreSQL Backup**")
        except Exception:
            pass

    if os.path.exists(backup_file):
        os.remove(backup_file)

    await msg.edit_text("✅ Backup sent to `LOGS_CHANNEL` and `OWNER_LIST`.")
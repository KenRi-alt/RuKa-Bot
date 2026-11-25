import os
import asyncio
from pyrogram import Client, filters
from RUKA import CONFIG
from ..utils.user_level import userLevel


@Client.on_message(filters.command("backup"))
@userLevel("OWNER", msg=True)
async def backup_postgres(client: Client, message):
    msg = await message.reply_text("⏳ Creating PostgreSQL backup...")
    backup_file = "ruka_postgres_backup.sql"

    proc = await asyncio.create_subprocess_exec(
        "pg_dump", CONFIG.DB_URL, "-f", backup_file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        return await msg.edit_text(f"❌ Backup failed:\n`{stderr.decode()}`")

    if CONFIG.LOGS_CHANNEL:
        await client.send_document(
            CONFIG.LOGS_CHANNEL,
            document=backup_file,
            caption="📦 **RuKa-Bot PostgreSQL Backup**"
        )

    for owner_id in CONFIG.OWNER_LIST:
        try:
            await client.send_document(
                owner_id,
                document=backup_file,
                caption="📦 **RuKa-Bot PostgreSQL Backup**"
            )
        except Exception:
            pass

    if os.path.exists(backup_file):
        os.remove(backup_file)

    await msg.edit_text("✅ Backup sent to `LOGS_CHANNEL` and `OWNER_LIST`.")
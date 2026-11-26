import json
from io import BytesIO
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from RUKA import CONFIG
from RUKA.utils.db import get_pool

router = Router()


@router.message(Command("backup", prefix="/!"))
async def backup_postgres(message: Message):
    if message.from_user.id not in (CONFIG.OWNER_LIST or []):
        return await message.answer("❌ Owner only!")

    msg = await message.answer("⏳ Exporting PostgreSQL backup...")
    try:
        pool = await get_pool()
        backup_data = {}
        async with pool.acquire() as conn:
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
            for t in tables:
                tname = t["tablename"]
                rows = await conn.fetch(f'SELECT * FROM "{tname}"')
                backup_data[tname] = [
                    {k: (str(v) if not isinstance(v, (int, float, bool, str, type(None))) else v) for k, v in dict(r).items()}
                    for r in rows
                ]

        raw = json.dumps(backup_data, indent=2).encode("utf-8")
        doc = BufferedInputFile(raw, filename="ruka_backup.json")

        if CONFIG.LOGS_CHANNEL:
            try:
                await message.bot.send_document(CONFIG.LOGS_CHANNEL, document=doc, caption="📦 **Ruka Database Backup**")
            except Exception:
                pass
        for oid in (CONFIG.OWNER_LIST or []):
            try:
                await message.bot.send_document(oid, document=BufferedInputFile(raw, filename="ruka_backup.json"), caption="📦 **Ruka Database Backup**")
            except Exception:
                pass

        await msg.edit_text("✅ Backup exported and sent to `LOGS_CHANNEL` & `OWNER_LIST`!")
    except Exception as e:
        await msg.edit_text(f"❌ Backup error: `{e}`")
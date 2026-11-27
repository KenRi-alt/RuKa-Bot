import os, asyncio, traceback, aiohttp
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ErrorEvent, InlineKeyboardMarkup, InlineKeyboardButton
from RUKA import LOGGER, CONFIG
from RUKA.utils.db import get_pool, get_bot_config, is_botbanned, is_gbanned, get_all_staff


async def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL", "https://ruka-bot-sy8s.onrender.com")
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(url, timeout=10) as resp:
                    LOGGER.info(f"[KEEP-ALIVE] {url} -> {resp.status}")
            except Exception:
                pass


async def _is_staff(uid: int) -> bool:
    if uid in (CONFIG.OWNER_LIST or []) or uid in (CONFIG.DEV_LIST or []) or uid in (CONFIG.SUDO_LIST or []):
        return True
    try:
        return uid in (await get_all_staff())
    except Exception:
        return False


async def guard_middleware(handler, event: Message, data: dict):
    if not getattr(event, "from_user", None) or event.from_user.is_bot:
        return await handler(event, data)
    uid = event.from_user.id

    try:
        # 1. Auto-kick GBanned users in groups
        if event.chat.type in ("group", "supergroup"):
            gr = await is_gbanned(uid)
            if gr:
                try:
                    await event.bot.ban_chat_member(event.chat.id, uid)
                    await event.answer(f"🌐 **GBanned User Removed:** {event.from_user.full_name} (`{gr}`)", parse_mode=None)
                except Exception:
                    pass
                return

        if not await _is_staff(uid):
            # 2. BotBan check
            if await is_botbanned(uid):
                return
            # 3. Maintenance check (only for commands)
            txt = event.text or ""
            if txt.startswith(("/", "!")):
                if (await get_bot_config("maintenance", "off")) == "on":
                    rsn = await get_bot_config("maintenance_reason", "Upgrading systems!")
                    return await event.answer(f"🛠️ **Ruka is under maintenance:**\n{rsn}", parse_mode=None)
                # 4. ForceSub check
                fs = await get_bot_config("forcesub")
                if fs:
                    try:
                        mem = await event.bot.get_chat_member(fs, uid)
                        if mem.status in ("left", "kicked"):
                            raise ValueError("Not joined")
                    except Exception:
                        url = f"https://t.me/{fs.lstrip('@')}" if str(fs).startswith("@") else "https://t.me/sup_ruka_bot"
                        btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Join Channel", url=url)]])
                        return await event.answer(f"🔒 **Join our channel first to use Ruka!**", reply_markup=btn)
    except Exception:
        pass

    return await handler(event, data)


async def main():
    db_status = "✅ Connected"
    try:
        await get_pool()
        LOGGER.info("[DB] PostgreSQL pool pre-warmed in RAM!")
    except Exception as e:
        db_status = f"⚠️ {e}"
        LOGGER.warning(f"[DB] Pre-warm skipped: {e}")

    bot = Bot(token=CONFIG.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()
    dp.message.outer_middleware(guard_middleware)

    @dp.errors()
    async def error_telemetry(event: ErrorEvent):
        err = "".join(traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__))[-1500:]
        LOGGER.error(f"[ERROR] {err}")
        if CONFIG.LOGS_CHANNEL:
            try:
                await bot.send_message(CONFIG.LOGS_CHANNEL, f"🚨 Error Telemetry:\n{err}", parse_mode=None)
            except Exception:
                pass

    from RUKA.plugins.start import router as start_router
    from RUKA.plugins.admin import router as admin_router
    from RUKA.plugins.owner_sudo import router as owner_router
    from RUKA.plugins.database import router as db_router
    from RUKA.plugins.settings_captcha import router as settings_router
    from RUKA.plugins.locks_misc import router as locks_router
    from RUKA.plugins.levels_games import router as games_router
    from RUKA.plugins.social import router as social_router
    from RUKA.plugins.fun_anime import router as fun_router
    from RUKA.plugins.extra_fun import router as extra_router
    from RUKA.plugins.ai_ruka import router as ai_router

    for r in (start_router, admin_router, owner_router, db_router, settings_router, locks_router, games_router, social_router, fun_router, extra_router, ai_router):
        dp.include_router(r)

    asyncio.create_task(keep_alive())
    LOGGER.info("Bot Online (aiogram 3 - Global Guard & Telemetry Active!)")

    for cid in {CONFIG.LOGS_CHANNEL, CONFIG.SUPPORT_CHAT_ID}:
        if cid:
            try:
                await bot.send_message(cid, f"💓 **Ruka Sarashina is Online!**\n• **Database:** `{db_status}`\n• **Guard & Telemetry:** `Active ⚡`")
            except Exception:
                pass

    await bot.delete_webhook(drop_pending_updates=True)
    while True:
        try:
            await dp.start_polling(bot, polling_timeout=30)
        except Exception as e:
            LOGGER.warning(f"[POLLING] Reconnecting: {e}")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
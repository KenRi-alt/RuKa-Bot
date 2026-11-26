import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from RUKA import LOGGER, CONFIG
from RUKA.utils.db import get_pool


# Keep Render Free Tier Awake (Self-pings every 10 mins)
async def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL", "https://ruka-bot-sy8s.onrender.com")
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(600)
            try:
                async with session.get(url, timeout=10) as resp:
                    LOGGER.info(f"[KEEP-ALIVE] Pinged {url} -> {resp.status}")
            except Exception:
                pass


async def main():
    # 1. Pre-warm PostgreSQL connection pool in RAM
    db_status = "✅ Connected"
    try:
        await get_pool()
        LOGGER.info("[DB] PostgreSQL pool pre-warmed in RAM!")
    except Exception as e:
        db_status = f"⚠️ {e}"
        LOGGER.warning(f"[DB] Pre-warm skipped: {e}")

    bot = Bot(
        token=CONFIG.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # 2. Register all routers (ai_ruka MUST be last because of its neuro chat watcher)
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

    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(owner_router)
    dp.include_router(db_router)
    dp.include_router(settings_router)
    dp.include_router(locks_router)
    dp.include_router(games_router)
    dp.include_router(social_router)
    dp.include_router(fun_router)
    dp.include_router(extra_router)
    dp.include_router(ai_router)

    # 3. Start background keep-alive task
    asyncio.create_task(keep_alive())

    LOGGER.info("Bot Online (aiogram 3 - High Speed & Anti-Sleep Active!)")

    # 4. Notify LOGS_CHANNEL and SUPPORT_CHAT_ID
    startup_msg = (
        "💓 **Ruka Sarashina is Online!**\n\n"
        f"• **Database:** `{db_status}`\n"
        "• **RAM Cache & Anti-Sleep:** `Active ⚡`"
    )
    notified = set()
    for chat_id in (CONFIG.LOGS_CHANNEL, CONFIG.SUPPORT_CHAT_ID):
        if chat_id and chat_id not in notified:
            notified.add(chat_id)
            try:
                await bot.send_message(chat_id, startup_msg)
            except Exception as err:
                LOGGER.info(f"Could not notify {chat_id}: {err}")

    await bot.delete_webhook(drop_pending_updates=True)

    # 5. Auto-recover polling loop
    while True:
        try:
            await dp.start_polling(bot, polling_timeout=30)
        except Exception as e:
            LOGGER.warning(f"[POLLING] Reconnecting after error: {e}")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
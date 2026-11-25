import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from RUKA import LOGGER, CONFIG


# Render Health Check Server (keeps Free Web Service alive)
async def health_check(request):
    return web.Response(text="RuKa-Bot is Online!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    LOGGER.info(f"[SERVER] Health check listener active on port {port}")


async def main():
    await start_web_server()

    bot = Bot(
        token=CONFIG.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    # Register all aiogram 3 plugin routers
    from RUKA.plugins.start import router as start_router
    from RUKA.plugins.fun_anime import router as fun_router
    from RUKA.plugins.ai_ruka import router as ai_router
    from RUKA.plugins.levels_games import router as games_router
    from RUKA.plugins.admin import router as admin_router
    from RUKA.plugins.owner_sudo import router as owner_router
    from RUKA.plugins.database import router as db_router
    from RUKA.plugins.settings_captcha import router as settings_router
    from RUKA.plugins.locks_misc import router as locks_router

    dp.include_router(start_router)
    dp.include_router(fun_router)
    dp.include_router(ai_router)
    dp.include_router(games_router)
    dp.include_router(admin_router)
    dp.include_router(owner_router)
    dp.include_router(db_router)
    dp.include_router(settings_router)
    dp.include_router(locks_router)

    LOGGER.info("Bot Online (aiogram 3 - Zero FloodWait!)")
    if CONFIG.SUPPORT_CHAT_ID:
        try:
            await bot.send_message(
                CONFIG.SUPPORT_CHAT_ID,
                "💓 **RuKa-Bot is Online!** (Powered by aiogram 3)"
            )
        except Exception as err:
            LOGGER.info(f"Could not notify support chat: {err}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
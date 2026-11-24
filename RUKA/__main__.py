import asyncio
from pyrogram import Client
from pyrogram.errors import FloodWait

from RUKA import LOGGER, CONFIG


async def notify_online(client: Client) -> None:
    LOGGER.info("[RUKA]: BOOTING.......")
    if not CONFIG.SUPPORT_CHAT_ID:
        return
    try:
        await client.send_message(CONFIG.SUPPORT_CHAT_ID, "Client Host is Online!")
    except Exception as err:
        LOGGER.info(f"Bot wasn't able to send message in your log Group\n\nERROR: {err}")


class Bot(Client):
    def __init__(self) -> None:
        super().__init__(
            "rukabot",
            api_id=CONFIG.API_ID,
            api_hash=CONFIG.API_HASH,
            bot_token=CONFIG.BOT_TOKEN,
            plugins={"root": "RUKA.plugins"},
        )

    async def start(self, *args, **kwargs):
        while True:
            try:
                await super().start(*args, **kwargs)
                break
            except FloodWait as e:
                LOGGER.warning(f"[RUKA]: FloodWait! Sleeping for {e.value} seconds...")
                await asyncio.sleep(e.value + 5)
        LOGGER.info("Bot Online")
        await notify_online(self)

    async def stop(self, *args, **kwargs):
        await super().stop(*args, **kwargs)
        LOGGER.info("Stopped Services")


if __name__ == "__main__":
    Bot().run()
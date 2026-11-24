import asyncpg
from RUKA import CONFIG

_POOL = None


async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(CONFIG.DB_URL, min_size=1, max_size=5)
        async with _POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id BIGINT PRIMARY KEY,
                    captcha BOOLEAN DEFAULT FALSE,
                    welcome BOOLEAN DEFAULT TRUE,
                    antilink BOOLEAN DEFAULT FALSE,
                    nightmode BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS chat_filters (
                    chat_id BIGINT,
                    keyword TEXT,
                    reply TEXT,
                    PRIMARY KEY (chat_id, keyword)
                );
            """)
    return _POOL


async def get_chat_settings(chat_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT captcha, welcome, antilink, nightmode FROM chat_settings WHERE chat_id=$1", chat_id)
        if not row:
            await conn.execute("INSERT INTO chat_settings (chat_id) VALUES ($1) ON CONFLICT DO NOTHING", chat_id)
            return {"captcha": False, "welcome": True, "antilink": False, "nightmode": False}
        return dict(row)


async def toggle_setting(chat_id: int, key: str) -> bool:
    pool = await get_pool()
    current = await get_chat_settings(chat_id)
    new_val = not current[key]
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE chat_settings SET {key}=$1 WHERE chat_id=$2", new_val, chat_id)
    return new_val


async def add_filter(chat_id: int, keyword: str, reply: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO chat_filters (chat_id, keyword, reply) VALUES ($1, $2, $3) "
            "ON CONFLICT (chat_id, keyword) DO UPDATE SET reply=$3",
            chat_id, keyword.lower(), reply
        )


async def remove_filter(chat_id: int, keyword: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_filters WHERE chat_id=$1 AND keyword=$2", chat_id, keyword.lower())


async def get_filters(chat_id: int) -> dict[str, str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT keyword, reply FROM chat_filters WHERE chat_id=$1", chat_id)
        return {r["keyword"]: r["reply"] for r in rows}
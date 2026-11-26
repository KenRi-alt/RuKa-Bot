import asyncpg
from RUKA import CONFIG

_POOL = None


async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(CONFIG.DB_URL, min_size=1, max_size=10)
        async with _POOL.acquire() as conn:
            # 1. Settings & Filters
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
            # 2. Marriage & Family (Nakama System)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS marriage_data (
                    user_id BIGINT PRIMARY KEY,
                    partner_id BIGINT,
                    marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS family_data (
                    user_id BIGINT,
                    parent_id BIGINT,
                    relation_type TEXT,
                    PRIMARY KEY (user_id, parent_id)
                );
            """)
            # 3. Gacha Collection (Permanent Card Storage)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gacha_collection (
                    user_id BIGINT,
                    card_id INTEGER,
                    card_name TEXT,
                    rarity TEXT,
                    power INTEGER,
                    image_url TEXT,
                    PRIMARY KEY (user_id, card_id)
                );
            """)
            # 4. Economy & XP (Persistent Stats)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id BIGINT PRIMARY KEY,
                    coins INTEGER DEFAULT 100,
                    xp INTEGER DEFAULT 0
                );
            """)
    return _POOL


# --- Chat Settings Helpers ---
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
    async with pool.acquire() as conn:
        current = await conn.fetchval(f"SELECT {key} FROM chat_settings WHERE chat_id=$1", chat_id)
        new_val = not current
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


# --- Marriage Helpers ---
async def get_partner(user_id: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT partner_id FROM marriage_data WHERE user_id=$1", user_id)


async def set_marriage(user_id: int, partner_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO marriage_data (user_id, partner_id) VALUES ($1, $2) "
            "ON CONFLICT (user_id) DO UPDATE SET partner_id=$2",
            user_id, partner_id
        )
        await conn.execute("INSERT INTO marriage_data (user_id, partner_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", partner_id, user_id)


async def remove_marriage(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        partner = await conn.fetchval("SELECT partner_id FROM marriage_data WHERE user_id=$1", user_id)
        if partner:
            await conn.execute("DELETE FROM marriage_data WHERE user_id=$1 OR partner_id=$1", user_id)


# --- Family Helpers ---
async def add_family_member(user_id: int, parent_id: int, relation: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO family_data (user_id, parent_id, relation_type) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            user_id, parent_id, relation
        )


async def get_family(user_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT parent_id, relation_type FROM family_data WHERE user_id=$1", user_id)
        return [dict(r) for r in rows]


# --- Gacha Helpers ---
async def add_gacha_card(user_id: int, card: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO gacha_collection (user_id, card_id, card_name, rarity, power, image_url) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
            user_id, card["id"], card["name"], card["rarity"], card["power"], card["url"]
        )


async def get_user_cards(user_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT card_id, card_name, rarity, power, image_url FROM gacha_collection WHERE user_id=$1", user_id)
        return [dict(r) for r in rows]


# --- Economy Helpers ---
async def get_user_stats(user_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT coins, xp FROM user_stats WHERE user_id=$1", user_id)
        if not row:
            await conn.execute("INSERT INTO user_stats (user_id, coins, xp) VALUES ($1, 100, 0)", user_id)
            return {"coins": 100, "xp": 0}
        return {"coins": row["coins"], "xp": row["xp"]}


async def update_user_stats(user_id: int, coins: int = None, xp: int = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if coins is not None:
            await conn.execute("UPDATE user_stats SET coins = coins + $1 WHERE user_id=$2", coins, user_id)
        if xp is not None:
            await conn.execute("UPDATE user_stats SET xp = xp + $1 WHERE user_id=$2", xp, user_id)


# --- Backup Helper ---
async def backup_postgres(db_url: str, file_path: str):
    proc = await asyncio.create_subprocess_exec(
        "pg_dump", db_url, "-f", file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    return proc.returncode, stderr.decode()
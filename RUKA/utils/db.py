import asyncpg
from RUKA import CONFIG

_POOL = None

async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(CONFIG.DB_URL, min_size=1, max_size=10)
        async with _POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_settings (chat_id BIGINT PRIMARY KEY, captcha BOOLEAN DEFAULT FALSE, welcome BOOLEAN DEFAULT TRUE, antilink BOOLEAN DEFAULT FALSE, nightmode BOOLEAN DEFAULT FALSE);
                CREATE TABLE IF NOT EXISTS chat_filters (chat_id BIGINT, keyword TEXT, reply TEXT, PRIMARY KEY (chat_id, keyword));
                CREATE TABLE IF NOT EXISTS marriage_data (user_id BIGINT PRIMARY KEY, partner_id BIGINT, marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS family_data (user_id BIGINT, relative_id BIGINT, relation_type TEXT, PRIMARY KEY (user_id, relative_id));
                CREATE TABLE IF NOT EXISTS gacha_collection (user_id BIGINT, card_id INTEGER, card_name TEXT, rarity TEXT, power INTEGER, image_url TEXT, PRIMARY KEY (user_id, card_id));
                CREATE TABLE IF NOT EXISTS user_stats (user_id BIGINT PRIMARY KEY, coins INTEGER DEFAULT 100, xp INTEGER DEFAULT 0);
            """)
    return _POOL

# --- Marriage & Family Helpers ---
async def set_marriage(u1: int, u2: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO marriage_data (user_id, partner_id) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET partner_id=$2", u1, u2)
        await conn.execute("INSERT INTO marriage_data (user_id, partner_id) VALUES ($1, $2) ON CONFLICT (user_id) DO UPDATE SET partner_id=$2", u2, u1)

async def get_partner(uid: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT partner_id FROM marriage_data WHERE user_id=$1", uid)

async def remove_marriage(uid: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        partner = await conn.fetchval("SELECT partner_id FROM marriage_data WHERE user_id=$1", uid)
        if partner:
            await conn.execute("DELETE FROM marriage_data WHERE user_id=$1 OR partner_id=$1", uid)

async def add_relation(uid: int, rel_id: int, rel_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO family_data (user_id, relative_id, relation_type) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", uid, rel_id, rel_type)

async def get_family(uid: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT relative_id, relation_type FROM family_data WHERE user_id=$1", uid)
        return [dict(r) for r in rows]

# --- Gacha Helpers ---
async def add_gacha_card(uid: int, card: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO gacha_collection (user_id, card_id, card_name, rarity, power, image_url) VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING", uid, card['id'], card['name'], card['rarity'], card['power'], card['url'])

async def get_user_cards(uid: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT card_id, card_name, rarity, power, image_url FROM gacha_collection WHERE user_id=$1", uid)
        return [dict(r) for r in rows]

# --- Stats Helpers ---
async def get_user_stats(uid: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT coins, xp FROM user_stats WHERE user_id=$1", uid)
        if not row:
            await conn.execute("INSERT INTO user_stats (user_id, coins, xp) VALUES ($1, 100, 0)", uid)
            return {"coins": 100, "xp": 0}
        return {"coins": row["coins"], "xp": row["xp"]}
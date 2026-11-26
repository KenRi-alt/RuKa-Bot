import asyncpg
from RUKA import CONFIG

_POOL = None


async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(CONFIG.DB_URL, min_size=1, max_size=10)
        async with _POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id BIGINT PRIMARY KEY,
                    captcha BOOLEAN DEFAULT FALSE,
                    welcome BOOLEAN DEFAULT TRUE,
                    antilink BOOLEAN DEFAULT FALSE,
                    nightmode BOOLEAN DEFAULT FALSE,
                    antiraid BOOLEAN DEFAULT FALSE,
                    cleanservice BOOLEAN DEFAULT FALSE,
                    cleancommand BOOLEAN DEFAULT FALSE
                );
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS antiraid BOOLEAN DEFAULT FALSE;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS cleanservice BOOLEAN DEFAULT FALSE;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS cleancommand BOOLEAN DEFAULT FALSE;

                CREATE TABLE IF NOT EXISTS chat_filters (
                    chat_id BIGINT, keyword TEXT, reply TEXT,
                    PRIMARY KEY (chat_id, keyword)
                );
                CREATE TABLE IF NOT EXISTS approved_users (
                    chat_id BIGINT, user_id BIGINT,
                    PRIMARY KEY (chat_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS disabled_cmds (
                    chat_id BIGINT, cmd TEXT,
                    PRIMARY KEY (chat_id, cmd)
                );
                CREATE TABLE IF NOT EXISTS log_channels (
                    chat_id BIGINT PRIMARY KEY,
                    log_id BIGINT
                );
                CREATE TABLE IF NOT EXISTS federations (
                    fed_id TEXT PRIMARY KEY,
                    fed_name TEXT,
                    owner_id BIGINT
                );
                CREATE TABLE IF NOT EXISTS fed_chats (
                    chat_id BIGINT PRIMARY KEY,
                    fed_id TEXT
                );
                CREATE TABLE IF NOT EXISTS fed_bans (
                    fed_id TEXT,
                    user_id BIGINT,
                    reason TEXT,
                    PRIMARY KEY (fed_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS marriage_data (
                    user_id BIGINT PRIMARY KEY, partner_id BIGINT,
                    marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS family_data (
                    user_id BIGINT, relative_id BIGINT, relation_type TEXT,
                    PRIMARY KEY (user_id, relative_id)
                );
                CREATE TABLE IF NOT EXISTS gacha_collection (
                    user_id BIGINT, card_id INTEGER, card_name TEXT,
                    rarity TEXT, power INTEGER, image_url TEXT,
                    PRIMARY KEY (user_id, card_id)
                );
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id BIGINT PRIMARY KEY,
                    coins INTEGER DEFAULT 100, xp INTEGER DEFAULT 0
                );
            """)
    return _POOL


# --- Chat Settings & Filters ---
async def get_chat_settings(chat_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT captcha, welcome, antilink, nightmode, antiraid, cleanservice, cleancommand "
            "FROM chat_settings WHERE chat_id=$1", chat_id
        )
        if not row:
            await conn.execute("INSERT INTO chat_settings (chat_id) VALUES ($1) ON CONFLICT DO NOTHING", chat_id)
            return {
                "captcha": False, "welcome": True, "antilink": False, "nightmode": False,
                "antiraid": False, "cleanservice": False, "cleancommand": False
            }
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


# --- Approval System ---
async def approve_user(chat_id: int, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO approved_users (chat_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", chat_id, user_id)


async def unapprove_user(chat_id: int, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM approved_users WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)


async def is_approved(chat_id: int, user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT 1 FROM approved_users WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
        return bool(val)


async def get_approved(chat_id: int) -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM approved_users WHERE chat_id=$1", chat_id)
        return [r["user_id"] for r in rows]


# --- Disabled Commands ---
async def disable_cmd(chat_id: int, cmd: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO disabled_cmds (chat_id, cmd) VALUES ($1, $2) ON CONFLICT DO NOTHING", chat_id, cmd.lower())


async def enable_cmd(chat_id: int, cmd: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM disabled_cmds WHERE chat_id=$1 AND cmd=$2", chat_id, cmd.lower())


async def get_disabled_cmds(chat_id: int) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT cmd FROM disabled_cmds WHERE chat_id=$1", chat_id)
        return [r["cmd"] for r in rows]


# --- Log Channels ---
async def set_log_channel(chat_id: int, log_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO log_channels (chat_id, log_id) VALUES ($1, $2) ON CONFLICT (chat_id) DO UPDATE SET log_id=$2", chat_id, log_id)


async def unset_log_channel(chat_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM log_channels WHERE chat_id=$1", chat_id)


async def get_log_channel(chat_id: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT log_id FROM log_channels WHERE chat_id=$1", chat_id)


# --- Federations ---
async def create_fed(fed_id: str, fed_name: str, owner_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO federations (fed_id, fed_name, owner_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", fed_id, fed_name, owner_id)


async def join_fed(chat_id: int, fed_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO fed_chats (chat_id, fed_id) VALUES ($1, $2) ON CONFLICT (chat_id) DO UPDATE SET fed_id=$2", chat_id, fed_id)


async def get_chat_fed(chat_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT fed_id FROM fed_chats WHERE chat_id=$1", chat_id)


async def fban_user(fed_id: str, user_id: int, reason: str = "Fed Banned"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO fed_bans (fed_id, user_id, reason) VALUES ($1, $2, $3) ON CONFLICT (fed_id, user_id) DO UPDATE SET reason=$3", fed_id, user_id, reason)


async def funban_user(fed_id: str, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM fed_bans WHERE fed_id=$1 AND user_id=$2", fed_id, user_id)


async def is_fbanned(fed_id: str, user_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT reason FROM fed_bans WHERE fed_id=$1 AND user_id=$2", fed_id, user_id)


# --- Marriage & Family ---
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


# --- Gacha & Stats ---
async def add_gacha_card(uid: int, card: dict):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO gacha_collection (user_id, card_id, card_name, rarity, power, image_url) "
            "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
            uid, card["id"], card["name"], card["rarity"], card["power"], card["url"]
        )


async def get_user_cards(uid: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT card_id, card_name, rarity, power, image_url FROM gacha_collection WHERE user_id=$1", uid)
        return [dict(r) for r in rows]


async def get_user_stats(uid: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT coins, xp FROM user_stats WHERE user_id=$1", uid)
        if not row:
            await conn.execute("INSERT INTO user_stats (user_id, coins, xp) VALUES ($1, 100, 0)", uid)
            return {"coins": 100, "xp": 0}
        return {"coins": row["coins"], "xp": row["xp"]}


async def update_user_stats(uid: int, coins: int = None, xp: int = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await get_user_stats(uid)
        if coins is not None:
            await conn.execute("UPDATE user_stats SET coins = GREATEST(0, coins + $1) WHERE user_id=$2", coins, uid)
        if xp is not None:
            await conn.execute("UPDATE user_stats SET xp = GREATEST(0, xp + $1) WHERE user_id=$2", xp, uid)
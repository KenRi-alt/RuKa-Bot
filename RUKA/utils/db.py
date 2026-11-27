import urllib.parse
import asyncpg
from RUKA import CONFIG

_POOL = None


def _clean_db_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    qs = urllib.parse.parse_qs(parsed.query)
    valid_ssl = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    if "sslmode" in qs and qs["sslmode"][0] not in valid_ssl:
        qs["sslmode"] = ["require"]
    new_query = urllib.parse.urlencode(qs, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


async def get_pool():
    global _POOL
    if _POOL is None:
        _POOL = await asyncpg.create_pool(_clean_db_url(CONFIG.DB_URL), min_size=1, max_size=10)
        async with _POOL.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    key TEXT PRIMARY KEY, value TEXT
                );
                CREATE TABLE IF NOT EXISTS bot_staff (
                    user_id BIGINT PRIMARY KEY, role TEXT
                );
                CREATE TABLE IF NOT EXISTS global_bans (
                    user_id BIGINT PRIMARY KEY, reason TEXT DEFAULT 'Global Ban'
                );
                CREATE TABLE IF NOT EXISTS bot_bans (
                    user_id BIGINT PRIMARY KEY, reason TEXT DEFAULT 'Banned from bot'
                );
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id BIGINT PRIMARY KEY,
                    captcha BOOLEAN DEFAULT FALSE, welcome BOOLEAN DEFAULT TRUE,
                    antilink BOOLEAN DEFAULT FALSE, nightmode BOOLEAN DEFAULT FALSE,
                    antiraid BOOLEAN DEFAULT FALSE, cleanservice BOOLEAN DEFAULT FALSE,
                    cleancommand BOOLEAN DEFAULT FALSE, warn_limit INTEGER DEFAULT 3,
                    flood_limit INTEGER DEFAULT 0
                );
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS antiraid BOOLEAN DEFAULT FALSE;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS cleanservice BOOLEAN DEFAULT FALSE;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS cleancommand BOOLEAN DEFAULT FALSE;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS warn_limit INTEGER DEFAULT 3;
                ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS flood_limit INTEGER DEFAULT 0;

                CREATE TABLE IF NOT EXISTS chat_filters (chat_id BIGINT, keyword TEXT, reply TEXT, PRIMARY KEY (chat_id, keyword));
                CREATE TABLE IF NOT EXISTS chat_locks (chat_id BIGINT, lock_type TEXT, PRIMARY KEY (chat_id, lock_type));
                CREATE TABLE IF NOT EXISTS chat_blacklists (chat_id BIGINT, word TEXT, PRIMARY KEY (chat_id, word));
                CREATE TABLE IF NOT EXISTS chat_warns (chat_id BIGINT, user_id BIGINT, count INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id));
                CREATE TABLE IF NOT EXISTS chat_rules (chat_id BIGINT PRIMARY KEY, rules TEXT);
                CREATE TABLE IF NOT EXISTS chat_notes (chat_id BIGINT, note_name TEXT, content TEXT, PRIMARY KEY (chat_id, note_name));
                CREATE TABLE IF NOT EXISTS approved_users (chat_id BIGINT, user_id BIGINT, PRIMARY KEY (chat_id, user_id));
                CREATE TABLE IF NOT EXISTS disabled_cmds (chat_id BIGINT, cmd TEXT, PRIMARY KEY (chat_id, cmd));
                CREATE TABLE IF NOT EXISTS log_channels (chat_id BIGINT PRIMARY KEY, log_id BIGINT);
                CREATE TABLE IF NOT EXISTS federations (fed_id TEXT PRIMARY KEY, fed_name TEXT, owner_id BIGINT);
                CREATE TABLE IF NOT EXISTS fed_chats (chat_id BIGINT PRIMARY KEY, fed_id TEXT);
                CREATE TABLE IF NOT EXISTS fed_bans (fed_id TEXT, user_id BIGINT, reason TEXT, PRIMARY KEY (fed_id, user_id));
                CREATE TABLE IF NOT EXISTS marriage_data (user_id BIGINT PRIMARY KEY, partner_id BIGINT, marriage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS family_data (user_id BIGINT, relative_id BIGINT, relation_type TEXT, PRIMARY KEY (user_id, relative_id));
                CREATE TABLE IF NOT EXISTS user_profile (user_id BIGINT PRIMARY KEY, gender TEXT DEFAULT 'Not Set', bio TEXT DEFAULT 'No bio set.');
                CREATE TABLE IF NOT EXISTS gacha_collection (
                    card_id SERIAL PRIMARY KEY, user_id BIGINT, card_name TEXT, char_type TEXT,
                    anime TEXT, rarity TEXT, power INTEGER, image_url TEXT
                );
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id BIGINT PRIMARY KEY, coins INTEGER DEFAULT 100, xp INTEGER DEFAULT 0, last_daily DOUBLE PRECISION DEFAULT 0
                );
                ALTER TABLE user_stats ADD COLUMN IF NOT EXISTS last_daily DOUBLE PRECISION DEFAULT 0;
                CREATE TABLE IF NOT EXISTS user_inventory (user_id BIGINT, item_key TEXT, qty INTEGER DEFAULT 1, PRIMARY KEY (user_id, item_key));
            """)
    return _POOL


# --- Bot Global Config, Staff, GBans & BotBans ---
async def set_bot_config(key: str, value: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if value is None:
            await conn.execute("DELETE FROM bot_config WHERE key=$1", key)
        else:
            await conn.execute("INSERT INTO bot_config VALUES ($1,$2) ON CONFLICT (key) DO UPDATE SET value=$2", key, value)


async def get_bot_config(key: str, default: str = None) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT value FROM bot_config WHERE key=$1", key)
        return val if val is not None else default


async def set_staff(uid: int, role: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if role is None:
            await conn.execute("DELETE FROM bot_staff WHERE user_id=$1", uid)
        else:
            await conn.execute("INSERT INTO bot_staff VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET role=$2", uid, role)


async def get_all_staff() -> dict[int, str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {r["user_id"]: r["role"] for r in await conn.fetch("SELECT user_id, role FROM bot_staff")}


async def set_gban(uid: int, reason: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if reason is None:
            await conn.execute("DELETE FROM global_bans WHERE user_id=$1", uid)
        else:
            await conn.execute("INSERT INTO global_bans VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET reason=$2", uid, reason)


async def is_gbanned(uid: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT reason FROM global_bans WHERE user_id=$1", uid)


async def get_all_gbans() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch("SELECT user_id, reason FROM global_bans")]


async def set_botban(uid: int, reason: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if reason is None:
            await conn.execute("DELETE FROM bot_bans WHERE user_id=$1", uid)
        else:
            await conn.execute("INSERT INTO bot_bans VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET reason=$2", uid, reason)


async def is_botbanned(uid: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT reason FROM bot_bans WHERE user_id=$1", uid)


# --- Settings, Locks, Warns, Rules, Notes ---
async def get_chat_settings(chat_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM chat_settings WHERE chat_id=$1", chat_id)
        if not row:
            await conn.execute("INSERT INTO chat_settings (chat_id) VALUES ($1) ON CONFLICT DO NOTHING", chat_id)
            return {"captcha": False, "welcome": True, "antilink": False, "nightmode": False, "antiraid": False, "cleanservice": False, "cleancommand": False, "warn_limit": 3, "flood_limit": 0}
        return dict(row)


async def toggle_setting(chat_id: int, key: str) -> bool:
    pool = await get_pool()
    cur = await get_chat_settings(chat_id)
    val = not cur[key]
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE chat_settings SET {key}=$1 WHERE chat_id=$2", val, chat_id)
    return val


async def set_chat_num(chat_id: int, key: str, val: int):
    await get_chat_settings(chat_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"UPDATE chat_settings SET {key}=$1 WHERE chat_id=$2", val, chat_id)


async def add_filter(chat_id: int, kw: str, reply: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO chat_filters VALUES ($1,$2,$3) ON CONFLICT (chat_id,keyword) DO UPDATE SET reply=$3", chat_id, kw.lower(), reply)


async def remove_filter(chat_id: int, kw: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_filters WHERE chat_id=$1 AND keyword=$2", chat_id, kw.lower())


async def get_filters(chat_id: int) -> dict[str, str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {r["keyword"]: r["reply"] for r in await conn.fetch("SELECT keyword, reply FROM chat_filters WHERE chat_id=$1", chat_id)}


async def set_lock(chat_id: int, lt: str, active: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if active: await conn.execute("INSERT INTO chat_locks VALUES ($1,$2) ON CONFLICT DO NOTHING", chat_id, lt.lower())
        else: await conn.execute("DELETE FROM chat_locks WHERE chat_id=$1 AND lock_type=$2", chat_id, lt.lower())


async def get_locks(chat_id: int) -> set[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {r["lock_type"] for r in await conn.fetch("SELECT lock_type FROM chat_locks WHERE chat_id=$1", chat_id)}


async def set_blacklist(chat_id: int, word: str, active: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if active: await conn.execute("INSERT INTO chat_blacklists VALUES ($1,$2) ON CONFLICT DO NOTHING", chat_id, word.lower())
        else: await conn.execute("DELETE FROM chat_blacklists WHERE chat_id=$1 AND word=$2", chat_id, word.lower())


async def get_blacklists(chat_id: int) -> set[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {r["word"] for r in await conn.fetch("SELECT word FROM chat_blacklists WHERE chat_id=$1", chat_id)}


async def update_warn(chat_id: int, user_id: int, delta: int = 1, reset: bool = False) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if reset:
            await conn.execute("DELETE FROM chat_warns WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)
            return 0
        cur = await conn.fetchval("SELECT count FROM chat_warns WHERE chat_id=$1 AND user_id=$2", chat_id, user_id) or 0
        new_val = max(0, cur + delta)
        await conn.execute("INSERT INTO chat_warns VALUES ($1,$2,$3) ON CONFLICT (chat_id,user_id) DO UPDATE SET count=$3", chat_id, user_id, new_val)
        return new_val


async def get_warns(chat_id: int, user_id: int) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count FROM chat_warns WHERE chat_id=$1 AND user_id=$2", chat_id, user_id) or 0


async def set_rules(chat_id: int, rules: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO chat_rules VALUES ($1,$2) ON CONFLICT (chat_id) DO UPDATE SET rules=$2", chat_id, rules)


async def get_rules(chat_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT rules FROM chat_rules WHERE chat_id=$1", chat_id)


async def save_note(chat_id: int, name: str, content: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO chat_notes VALUES ($1,$2,$3) ON CONFLICT (chat_id,note_name) DO UPDATE SET content=$3", chat_id, name.lower(), content)


async def get_note(chat_id: int, name: str) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT content FROM chat_notes WHERE chat_id=$1 AND note_name=$2", chat_id, name.lower())


async def get_notes(chat_id: int) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [r["note_name"] for r in await conn.fetch("SELECT note_name FROM chat_notes WHERE chat_id=$1", chat_id)]


async def delete_note(chat_id: int, name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM chat_notes WHERE chat_id=$1 AND note_name=$2", chat_id, name.lower())


async def approve_user(chat_id: int, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO approved_users VALUES ($1,$2) ON CONFLICT DO NOTHING", chat_id, user_id)


async def unapprove_user(chat_id: int, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM approved_users WHERE chat_id=$1 AND user_id=$2", chat_id, user_id)


async def is_approved(chat_id: int, user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return bool(await conn.fetchval("SELECT 1 FROM approved_users WHERE chat_id=$1 AND user_id=$2", chat_id, user_id))


async def get_approved(chat_id: int) -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [r["user_id"] for r in await conn.fetch("SELECT user_id FROM approved_users WHERE chat_id=$1", chat_id)]


async def disable_cmd(chat_id: int, cmd: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO disabled_cmds VALUES ($1,$2) ON CONFLICT DO NOTHING", chat_id, cmd.lower())


async def enable_cmd(chat_id: int, cmd: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM disabled_cmds WHERE chat_id=$1 AND cmd=$2", chat_id, cmd.lower())


async def get_disabled_cmds(chat_id: int) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [r["cmd"] for r in await conn.fetch("SELECT cmd FROM disabled_cmds WHERE chat_id=$1", chat_id)]


async def set_log_channel(chat_id: int, log_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO log_channels VALUES ($1,$2) ON CONFLICT (chat_id) DO UPDATE SET log_id=$2", chat_id, log_id)


async def unset_log_channel(chat_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM log_channels WHERE chat_id=$1", chat_id)


async def get_log_channel(chat_id: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT log_id FROM log_channels WHERE chat_id=$1", chat_id)


async def create_fed(fed_id: str, fed_name: str, owner_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO federations VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", fed_id, fed_name, owner_id)


async def join_fed(chat_id: int, fed_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO fed_chats VALUES ($1,$2) ON CONFLICT (chat_id) DO UPDATE SET fed_id=$2", chat_id, fed_id)


async def get_chat_fed(chat_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT fed_id FROM fed_chats WHERE chat_id=$1", chat_id)


async def fban_user(fed_id: str, user_id: int, reason: str = "Fed Banned"):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO fed_bans VALUES ($1,$2,$3) ON CONFLICT (fed_id,user_id) DO UPDATE SET reason=$3", fed_id, user_id, reason)


async def funban_user(fed_id: str, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM fed_bans WHERE fed_id=$1 AND user_id=$2", fed_id, user_id)


async def is_fbanned(fed_id: str, user_id: int) -> str | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT reason FROM fed_bans WHERE fed_id=$1 AND user_id=$2", fed_id, user_id)


async def set_marriage(u1: int, u2: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO marriage_data (user_id, partner_id) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET partner_id=$2", u1, u2)
        await conn.execute("INSERT INTO marriage_data (user_id, partner_id) VALUES ($1,$2) ON CONFLICT (user_id) DO UPDATE SET partner_id=$2", u2, u1)


async def get_partner(uid: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT partner_id FROM marriage_data WHERE user_id=$1", uid)


async def remove_marriage(uid: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM marriage_data WHERE user_id=$1 OR partner_id=$1", uid)


async def add_relation(uid: int, rel_id: int, rel_type: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO family_data VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", uid, rel_id, rel_type)


async def remove_relation(uid: int, rel_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM family_data WHERE (user_id=$1 AND relative_id=$2) OR (user_id=$2 AND relative_id=$1)", uid, rel_id)


async def runaway_family(uid: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM family_data WHERE relative_id=$1 OR user_id=$1", uid)


async def get_family(uid: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch("SELECT relative_id, relation_type FROM family_data WHERE user_id=$1", uid)]


async def set_profile(uid: int, gender: str = None, bio: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO user_profile (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)
        if gender: await conn.execute("UPDATE user_profile SET gender=$1 WHERE user_id=$2", gender, uid)
        if bio: await conn.execute("UPDATE user_profile SET bio=$1 WHERE user_id=$2", bio, uid)


async def get_profile(uid: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT gender, bio FROM user_profile WHERE user_id=$1", uid)
        return dict(row) if row else {"gender": "Not Set", "bio": "No bio set."}


async def add_gacha_card(uid: int, name: str, char_type: str, anime: str, rarity: str, power: int, url: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO gacha_collection (user_id, card_name, char_type, anime, rarity, power, image_url) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING card_id", uid, name, char_type, anime, rarity, power, url
        )


async def get_user_cards(uid: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch("SELECT * FROM gacha_collection WHERE user_id=$1 ORDER BY card_id DESC", uid)]


async def get_user_stats(uid: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT coins, xp, last_daily FROM user_stats WHERE user_id=$1", uid)
        if not row:
            await conn.execute("INSERT INTO user_stats (user_id) VALUES ($1) ON CONFLICT DO NOTHING", uid)
            return {"coins": 100, "xp": 0, "last_daily": 0.0}
        return dict(row)


async def update_user_stats(uid: int, coins: int = None, xp: int = None, daily_ts: float = None):
    await get_user_stats(uid)
    pool = await get_pool()
    async with pool.acquire() as conn:
        if coins is not None: await conn.execute("UPDATE user_stats SET coins = GREATEST(0, coins + $1) WHERE user_id=$2", coins, uid)
        if xp is not None: await conn.execute("UPDATE user_stats SET xp = GREATEST(0, xp + $1) WHERE user_id=$2", xp, uid)
        if daily_ts is not None: await conn.execute("UPDATE user_stats SET last_daily=$1 WHERE user_id=$2", daily_ts, uid)


async def add_inventory_item(uid: int, item_key: str, qty: int = 1):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO user_inventory VALUES ($1,$2,$3) ON CONFLICT (user_id,item_key) DO UPDATE SET qty = user_inventory.qty + $3", uid, item_key, qty)


async def get_inventory(uid: int) -> dict[str, int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {r["item_key"]: r["qty"] for r in await conn.fetch("SELECT item_key, qty FROM user_inventory WHERE user_id=$1 AND qty > 0", uid)}
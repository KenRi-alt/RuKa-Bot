import os
import asyncpg
import logging

log = logging.getLogger("RUKA.Database")

async def init_ruka_database():
    """
    Initializes Ruka's relational tables (BPM, Affection Tiers, and Mod Logs)
    directly using your existing DB_URL connection.
    """
    db_url = os.environ.get("DB_URL")
    if not db_url:
        return

    try:
        connection = await asyncpg.connect(db_url)
        
        # 1. User Affection & Heartbeat Table
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS ruka_user_stats (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                bpm INT DEFAULT 75,
                affection_tier TEXT DEFAULT 'Trial Partner',
                messages_sent BIGINT DEFAULT 0,
                warnings INT DEFAULT 0,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Administrative Audit Ledger for Moderation Actions
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS ruka_mod_logs (
                log_id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                admin_id BIGINT,
                target_id BIGINT,
                action TEXT,
                reason TEXT,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        await connection.close()
        log.info("[RUKA] Girlfriend state schemas and moderation logs successfully initialized.")
    except Exception as e:
        log.error(f"[RUKA DB ERROR] Failed to initialize tables: {e}")

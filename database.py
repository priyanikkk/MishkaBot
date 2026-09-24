"""SQLite database layer using aiosqlite for MishkaBot."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiosqlite

from utils.mishka import MishkaRarity


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        # Ensure parent directory exists
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Initialize tables and indices in SQLite."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # Users table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT,
                    common_count INTEGER NOT NULL DEFAULT 0,
                    rare_count INTEGER NOT NULL DEFAULT 0,
                    epic_count INTEGER NOT NULL DEFAULT 0,
                    legendary_count INTEGER NOT NULL DEFAULT 0,
                    total_count INTEGER NOT NULL DEFAULT 0,
                    first_drop_at TEXT,
                    last_drop_at TEXT
                );
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_total ON users(total_count DESC);"
            )

            # Global bot statistics table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_stats (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await db.execute(
                "INSERT OR IGNORE INTO bot_stats (key, value) VALUES ('messages_processed', 0);"
            )
            await db.commit()

    async def increment_messages_processed(self, amount: int = 1) -> None:
        """Atomically increment total processed messages count."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO bot_stats (key, value) VALUES ('messages_processed', ?)
                ON CONFLICT(key) DO UPDATE SET value = value + ?;
                """,
                (amount, amount),
            )
            await db.commit()

    async def record_drop(
        self,
        user_id: int,
        first_name: str,
        username: Optional[str] = None,
        last_name: Optional[str] = None,
        rarity: MishkaRarity = MishkaRarity.COMMON,
    ) -> Dict[str, Any]:
        """
        Record a mishka drop for a user atomically.
        Creates the user row if not exists or updates counts and timestamps.
        """
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        col_map = {
            MishkaRarity.COMMON: "common_count",
            MishkaRarity.RARE: "rare_count",
            MishkaRarity.EPIC: "epic_count",
            MishkaRarity.LEGENDARY: "legendary_count",
        }
        target_column = col_map[rarity]

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Upsert user record
            query = f"""
                INSERT INTO users (
                    user_id, username, first_name, last_name,
                    {target_column}, total_count, first_drop_at, last_drop_at
                ) VALUES (?, ?, ?, ?, 1, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    {target_column} = {target_column} + 1,
                    total_count = total_count + 1,
                    last_drop_at = excluded.last_drop_at;
            """
            await db.execute(
                query,
                (user_id, username, first_name, last_name, now_iso, now_iso),
            )
            await db.commit()

            # Retrieve updated user stats
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?;", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {}

    async def get_user_stats(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get mishka statistics for a specific user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?;", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard of top users sorted by total mishkas."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM users
                WHERE total_count > 0
                ORDER BY total_count DESC, last_drop_at ASC
                LIMIT ?;
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_bot_stats(self) -> Dict[str, Any]:
        """Aggregate global statistics of the bot."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Messages processed
            async with db.execute(
                "SELECT value FROM bot_stats WHERE key = 'messages_processed';"
            ) as cursor:
                row = await cursor.fetchone()
                messages_processed = row["value"] if row else 0

            # Sum of mishkas by type and total users
            async with db.execute(
                """
                SELECT
                    COUNT(user_id) AS total_users,
                    COALESCE(SUM(total_count), 0) AS total_mishkas,
                    COALESCE(SUM(common_count), 0) AS common_total,
                    COALESCE(SUM(rare_count), 0) AS rare_total,
                    COALESCE(SUM(epic_count), 0) AS epic_total,
                    COALESCE(SUM(legendary_count), 0) AS legendary_total
                FROM users
                WHERE total_count > 0;
                """
            ) as cursor:
                row = await cursor.fetchone()
                return {
                    "messages_processed": messages_processed,
                    "total_users": row["total_users"] if row else 0,
                    "total_mishkas": row["total_mishkas"] if row else 0,
                    "common_total": row["common_total"] if row else 0,
                    "rare_total": row["rare_total"] if row else 0,
                    "epic_total": row["epic_total"] if row else 0,
                    "legendary_total": row["legendary_total"] if row else 0,
                }

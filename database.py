"""SQLite database layer for logging real Telegram Gift transactions and deduplication."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiosqlite


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Initialize SQLite tables for gift delivery history and metrics."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")

            # Table for real gift drops audit log
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS gift_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    first_name TEXT NOT NULL,
                    last_name TEXT,
                    gift_id TEXT NOT NULL,
                    star_cost INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_deliveries_user ON gift_deliveries(user_id);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_deliveries_status ON gift_deliveries(status);"
            )

            # Table for global message counter
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_metrics (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            await db.execute(
                "INSERT OR IGNORE INTO bot_metrics (key, value) VALUES ('messages_processed', 0);"
            )

            await db.commit()

    async def increment_messages_processed(self, amount: int = 1) -> None:
        """Atomically increment total processed messages count."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO bot_metrics (key, value) VALUES ('messages_processed', ?)
                ON CONFLICT(key) DO UPDATE SET value = value + ?;
                """,
                (amount, amount),
            )
            await db.commit()

    async def record_gift_delivery(
        self,
        user_id: int,
        first_name: str,
        gift_id: str,
        star_cost: int,
        status: str,
        username: Optional[str] = None,
        last_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> int:
        """Record real gift drop attempt and result."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO gift_deliveries (
                    user_id, username, first_name, last_name,
                    gift_id, star_cost, status, error_message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    user_id,
                    username,
                    first_name,
                    last_name,
                    gift_id,
                    star_cost,
                    status,
                    error_message,
                    now_iso,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0

    async def get_user_gifts_stats(self, user_id: int) -> Dict[str, Any]:
        """Get statistics of real gifts successfully received by user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT
                    COUNT(id) AS total_gifts_received,
                    COALESCE(SUM(star_cost), 0) AS total_stars_value,
                    MAX(created_at) AS last_gift_at
                FROM gift_deliveries
                WHERE user_id = ? AND status = 'SUCCESS';
                """,
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else {
                    "total_gifts_received": 0,
                    "total_stars_value": 0,
                    "last_gift_at": None,
                }

    async def get_top_receivers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get leaderboard of top users by real gifts received."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT
                    user_id,
                    username,
                    first_name,
                    COUNT(id) AS total_gifts,
                    SUM(star_cost) AS total_stars,
                    MAX(created_at) AS last_gift_at
                FROM gift_deliveries
                WHERE status = 'SUCCESS'
                GROUP BY user_id
                ORDER BY total_gifts DESC, total_stars DESC
                LIMIT ?;
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_global_gift_stats(self) -> Dict[str, Any]:
        """Get global metrics on processed messages and real gifts sent."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                "SELECT value FROM bot_metrics WHERE key = 'messages_processed';"
            ) as cursor:
                row = await cursor.fetchone()
                messages_count = row["value"] if row else 0

            async with db.execute(
                """
                SELECT
                    COUNT(id) AS total_sent,
                    COALESCE(SUM(star_cost), 0) AS total_stars_spent,
                    COUNT(DISTINCT user_id) AS unique_winners
                FROM gift_deliveries
                WHERE status = 'SUCCESS';
                """
            ) as cursor:
                row = await cursor.fetchone()
                return {
                    "messages_processed": messages_count,
                    "total_gifts_sent": row["total_sent"] if row else 0,
                    "total_stars_spent": row["total_stars_spent"] if row else 0,
                    "unique_winners": row["unique_winners"] if row else 0,
                }

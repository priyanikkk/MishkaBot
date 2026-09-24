"""Unit tests for Telegram Gifts & Stars bot: config, database, and gifts service."""

import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Gift, Gifts, StarAmount

from config import Config, ConfigValidationError, load_config, update_env_variable
from database import Database
from utils.gifts import GiftService
from utils.helpers import escape_html, format_user_mention, is_rate_limited


class TestConfig(unittest.TestCase):
    """Tests for configuration validation and .env file updating."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.env_file = Path(self.temp_dir) / ".env"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_config(self) -> None:
        self.env_file.write_text(
            "BOT_TOKEN=123456:ABC-DEF\n"
            "GIFT_DROP_CHANCE=10\n"
            "TARGET_CHAT_ID=-100123456789\n"
            "MAX_GIFT_PRICE_STARS=100\n"
            "ENABLED_GIFT_IDS=gift1,gift2\n"
            "ADMIN_IDS=111,222\n",
            encoding="utf-8",
        )
        cfg = load_config(self.env_file)
        self.assertEqual(cfg.bot_token, "123456:ABC-DEF")
        self.assertEqual(cfg.gift_drop_chance, 10.0)
        self.assertEqual(cfg.target_chat_id, -100123456789)
        self.assertEqual(cfg.max_gift_price_stars, 100)
        self.assertEqual(cfg.enabled_gift_ids, {"gift1", "gift2"})
        self.assertEqual(cfg.admin_ids, {111, 222})

    def test_missing_token_raises_error(self) -> None:
        self.env_file.write_text("BOT_TOKEN=\nGIFT_DROP_CHANCE=5\n", encoding="utf-8")
        os.environ.pop("BOT_TOKEN", None)
        with self.assertRaises(ConfigValidationError):
            load_config(self.env_file)

    def test_invalid_chance_raises_error(self) -> None:
        self.env_file.write_text("BOT_TOKEN=123:ABC\nGIFT_DROP_CHANCE=150\n", encoding="utf-8")
        with self.assertRaises(ConfigValidationError):
            load_config(self.env_file)

    def test_update_env_variable(self) -> None:
        self.env_file.write_text("BOT_TOKEN=123:ABC\nGIFT_DROP_CHANCE=5\n", encoding="utf-8")
        update_env_variable("GIFT_DROP_CHANCE", 15, self.env_file)
        content = self.env_file.read_text(encoding="utf-8")
        self.assertIn("GIFT_DROP_CHANCE=15", content)


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    """Tests for SQLite real gift audit logging."""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_bot.db")
        self.db = Database(self.db_path)
        await self.db.init_db()

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_increment_messages(self) -> None:
        await self.db.increment_messages_processed(10)
        stats = await self.db.get_global_gift_stats()
        self.assertEqual(stats["messages_processed"], 10)

    async def test_record_gift_delivery_and_stats(self) -> None:
        # Record successful delivery
        row_id = await self.db.record_gift_delivery(
            user_id=101,
            first_name="Иван",
            username="ivan",
            gift_id="gift_gold_star",
            star_cost=50,
            status="SUCCESS",
        )
        self.assertTrue(row_id > 0)

        # Record failed delivery
        await self.db.record_gift_delivery(
            user_id=102,
            first_name="Анна",
            gift_id="gift_box",
            star_cost=25,
            status="FAILED",
            error_message="STARGIFT_USAGE_LIMITED",
        )

        # Check user 101 stats
        u1_stats = await self.db.get_user_gifts_stats(101)
        self.assertEqual(u1_stats["total_gifts_received"], 1)
        self.assertEqual(u1_stats["total_stars_value"], 50)
        self.assertIsNotNone(u1_stats["last_gift_at"])

        # Check user 102 stats (failed delivery should not count towards received gifts)
        u2_stats = await self.db.get_user_gifts_stats(102)
        self.assertEqual(u2_stats["total_gifts_received"], 0)

        # Check leaderboard
        top = await self.db.get_top_receivers()
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["user_id"], 101)

        # Check global metrics
        global_stats = await self.db.get_global_gift_stats()
        self.assertEqual(global_stats["total_gifts_sent"], 1)
        self.assertEqual(global_stats["total_stars_spent"], 50)
        self.assertEqual(global_stats["unique_winners"], 1)


class TestGiftService(unittest.IsolatedAsyncioTestCase):
    """Tests for real Telegram Gifts & Stars selection logic."""

    def create_mock_gift(self, gift_id: str, star_count: int, remaining: int = None) -> Gift:
        g = MagicMock(spec=Gift)
        g.id = gift_id
        g.star_count = star_count
        g.remaining_count = remaining
        return g

    async def test_select_gift_insufficient_balance(self) -> None:
        service = GiftService()
        bot = MagicMock()
        bot.get_my_star_balance = AsyncMock(return_value=StarAmount(amount=0, nanostar_amount=0))
        cfg = Config(bot_token="test")

        gift, balance, status = await service.select_gift_for_drop(bot, cfg)
        self.assertIsNone(gift)
        self.assertEqual(balance, 0)
        self.assertEqual(status, "INSUFFICIENT_BALANCE")

    async def test_select_gift_filtered_by_price_and_id(self) -> None:
        service = GiftService()
        bot = MagicMock()
        bot.get_my_star_balance = AsyncMock(return_value=StarAmount(amount=100, nanostar_amount=0))

        g1 = self.create_mock_gift("g1", 15)
        g2 = self.create_mock_gift("g2", 80)
        g3 = self.create_mock_gift("g3", 150)  # Too expensive for balance

        service.get_available_gifts = AsyncMock(return_value=[g1, g2, g3])

        # Test max price limit: only g1 (15 <= 50)
        cfg = Config(bot_token="test", max_gift_price_stars=50)
        gift, balance, status = await service.select_gift_for_drop(bot, cfg)
        self.assertIsNotNone(gift)
        self.assertEqual(gift.id, "g1")
        self.assertEqual(status, "OK")

        # Test enabled filter
        cfg_enabled = Config(bot_token="test", enabled_gift_ids={"g2"})
        gift2, _, status2 = await service.select_gift_for_drop(bot, cfg_enabled)
        self.assertIsNotNone(gift2)
        self.assertEqual(gift2.id, "g2")
        self.assertEqual(status2, "OK")


class TestHelpers(unittest.TestCase):
    def test_rate_limiting(self) -> None:
        uid = 55555
        self.assertFalse(is_rate_limited(uid, 0.5))
        self.assertTrue(is_rate_limited(uid, 0.5))
        time.sleep(0.55)
        self.assertFalse(is_rate_limited(uid, 0.5))

    def test_formatting(self) -> None:
        self.assertEqual(format_user_mention(1, "Test", "user"), "@user")
        self.assertEqual(format_user_mention(1, "Test", None), '<a href="tg://user?id=1">Test</a>')
        self.assertEqual(escape_html("<b>&</b>"), "&lt;b&gt;&amp;&lt;/b&gt;")


if __name__ == "__main__":
    unittest.main()

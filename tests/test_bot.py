"""Comprehensive automated tests for MishkaBot."""

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from config import Config, ConfigValidationError, load_config, update_env_variable
from database import Database
from utils.helpers import escape_html, format_user_mention, is_rate_limited
from utils.mishka import (
    MishkaRarity,
    MISHKA_TYPES,
    parse_rarity,
    roll_mishka_drop,
)


class TestConfig(unittest.TestCase):
    """Tests for configuration parsing, validation and .env file updating."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.env_file = Path(self.temp_dir) / ".env"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_valid_config(self) -> None:
        self.env_file.write_text(
            "BOT_TOKEN=test_token_12345\n"
            "MISHKA_CHANCE=5\n"
            "COMMON_MISHKA_CHANCE=70\n"
            "RARE_MISHKA_CHANCE=20\n"
            "EPIC_MISHKA_CHANCE=8\n"
            "LEGENDARY_MISHKA_CHANCE=2\n"
            "DATABASE_PATH=test_data.db\n"
            "ADMIN_IDS=111,222\n",
            encoding="utf-8",
        )
        cfg = load_config(self.env_file)
        self.assertEqual(cfg.bot_token, "test_token_12345")
        self.assertEqual(cfg.mishka_chance, 5.0)
        self.assertEqual(cfg.common_chance, 70.0)
        self.assertEqual(cfg.rare_chance, 20.0)
        self.assertEqual(cfg.epic_chance, 8.0)
        self.assertEqual(cfg.legendary_chance, 2.0)
        self.assertEqual(cfg.admin_ids, {111, 222})

    def test_invalid_sum_raises_error(self) -> None:
        # Sum is 70 + 20 + 8 + 1 = 99 (not 100)
        self.env_file.write_text(
            "BOT_TOKEN=test_token\n"
            "COMMON_MISHKA_CHANCE=70\n"
            "RARE_MISHKA_CHANCE=20\n"
            "EPIC_MISHKA_CHANCE=8\n"
            "LEGENDARY_MISHKA_CHANCE=1\n",
            encoding="utf-8",
        )
        with self.assertRaises(ConfigValidationError) as ctx:
            load_config(self.env_file)
        self.assertIn("Сумма вероятностей типов мишек должна быть ровно 100%", str(ctx.exception))

    def test_missing_token_raises_error(self) -> None:
        self.env_file.write_text(
            "BOT_TOKEN=\n"
            "COMMON_MISHKA_CHANCE=70\n"
            "RARE_MISHKA_CHANCE=20\n"
            "EPIC_MISHKA_CHANCE=8\n"
            "LEGENDARY_MISHKA_CHANCE=2\n",
            encoding="utf-8",
        )
        # Clear system BOT_TOKEN if present
        os.environ.pop("BOT_TOKEN", None)
        with self.assertRaises(ConfigValidationError) as ctx:
            load_config(self.env_file)
        self.assertIn("BOT_TOKEN не задан", str(ctx.exception))

    def test_update_env_variable(self) -> None:
        self.env_file.write_text(
            "BOT_TOKEN=old_token\nMISHKA_CHANCE=5\n",
            encoding="utf-8",
        )
        update_env_variable("MISHKA_CHANCE", 10, self.env_file)
        content = self.env_file.read_text(encoding="utf-8")
        self.assertIn("MISHKA_CHANCE=10", content)
        self.assertNotIn("MISHKA_CHANCE=5", content)

        # Test adding new variable
        update_env_variable("NEW_VAR", "hello", self.env_file)
        content = self.env_file.read_text(encoding="utf-8")
        self.assertIn("NEW_VAR=hello", content)


class TestMishkaMechanics(unittest.TestCase):
    """Tests for RNG, rarities, and formatting."""

    def test_parse_rarity(self) -> None:
        self.assertEqual(parse_rarity("common"), MishkaRarity.COMMON)
        self.assertEqual(parse_rarity("Обычный"), MishkaRarity.COMMON)
        self.assertEqual(parse_rarity("rare"), MishkaRarity.RARE)
        self.assertEqual(parse_rarity("редкий"), MishkaRarity.RARE)
        self.assertEqual(parse_rarity("epic"), MishkaRarity.EPIC)
        self.assertEqual(parse_rarity("эпик"), MishkaRarity.EPIC)
        self.assertEqual(parse_rarity("legendary"), MishkaRarity.LEGENDARY)
        self.assertEqual(parse_rarity("легенда"), MishkaRarity.LEGENDARY)
        self.assertIsNone(parse_rarity("unknown_type"))

    def test_roll_zero_chance(self) -> None:
        for _ in range(100):
            dropped, info = roll_mishka_drop(0.0, 70, 20, 8, 2)
            self.assertFalse(dropped)
            self.assertIsNone(info)

    def test_roll_hundred_percent_chance(self) -> None:
        for _ in range(50):
            dropped, info = roll_mishka_drop(100.0, 70, 20, 8, 2)
            self.assertTrue(dropped)
            self.assertIsNotNone(info)
            self.assertIn(info.rarity, list(MishkaRarity))

    def test_rarity_distribution_simulation(self) -> None:
        counts = {r: 0 for r in MishkaRarity}
        total_rolls = 10000

        for _ in range(total_rolls):
            dropped, info = roll_mishka_drop(100.0, 70, 20, 8, 2)
            counts[info.rarity] += 1

        common_pct = counts[MishkaRarity.COMMON] / total_rolls * 100
        rare_pct = counts[MishkaRarity.RARE] / total_rolls * 100
        epic_pct = counts[MishkaRarity.EPIC] / total_rolls * 100
        leg_pct = counts[MishkaRarity.LEGENDARY] / total_rolls * 100

        # Tolerances for 10k rolls with ~99.9% binomial confidence
        self.assertTrue(66.0 <= common_pct <= 74.0, f"Common pct: {common_pct}%")
        self.assertTrue(17.0 <= rare_pct <= 23.0, f"Rare pct: {rare_pct}%")
        self.assertTrue(6.0 <= epic_pct <= 10.5, f"Epic pct: {epic_pct}%")
        self.assertTrue(1.0 <= leg_pct <= 3.5, f"Legendary pct: {leg_pct}%")

    def test_formatting_helpers(self) -> None:
        mention_with_uname = format_user_mention(123, "Иван", "ivan_bear")
        self.assertEqual(mention_with_uname, "@ivan_bear")

        mention_no_uname = format_user_mention(123, "Иван <3", None)
        self.assertEqual(mention_no_uname, '<a href="tg://user?id=123">Иван &lt;3</a>')

        self.assertEqual(escape_html("Hello <b>world</b> & friends"), "Hello &lt;b&gt;world&lt;/b&gt; &amp; friends")

    def test_rate_limiting(self) -> None:
        uid = 9999999
        # First call: not limited
        self.assertFalse(is_rate_limited(uid, cooldown_seconds=0.5))
        # Immediate second call: limited
        self.assertTrue(is_rate_limited(uid, cooldown_seconds=0.5))
        # After cooldown: not limited
        time.sleep(0.55)
        self.assertFalse(is_rate_limited(uid, cooldown_seconds=0.5))


class TestDatabase(unittest.IsolatedAsyncioTestCase):
    """Tests for asynchronous SQLite database layer."""

    async def asyncSetUpself(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test_mishka.db")
        self.db = Database(self.db_path)
        await self.db.init_db()

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_increment_messages_processed(self) -> None:
        await self.asyncSetUpself()
        try:
            await self.db.increment_messages_processed(5)
            await self.db.increment_messages_processed(3)
            stats = await self.db.get_bot_stats()
            self.assertEqual(stats["messages_processed"], 8)
        finally:
            await self.asyncTearDown()

    async def test_record_drops_and_user_stats(self) -> None:
        await self.asyncSetUpself()
        try:
            # User 1 gets common and rare
            await self.db.record_drop(
                user_id=101,
                first_name="Алиса",
                username="alice",
                rarity=MishkaRarity.COMMON,
            )
            await self.db.record_drop(
                user_id=101,
                first_name="Алиса",
                username="alice",
                rarity=MishkaRarity.RARE,
            )
            await self.db.record_drop(
                user_id=101,
                first_name="Алиса",
                username="alice",
                rarity=MishkaRarity.COMMON,
            )

            # User 2 gets legendary
            await self.db.record_drop(
                user_id=102,
                first_name="Боб",
                username="bob",
                rarity=MishkaRarity.LEGENDARY,
            )

            # Check User 1 stats
            u1 = await self.db.get_user_stats(101)
            self.assertIsNotNone(u1)
            self.assertEqual(u1["common_count"], 2)
            self.assertEqual(u1["rare_count"], 1)
            self.assertEqual(u1["epic_count"], 0)
            self.assertEqual(u1["legendary_count"], 0)
            self.assertEqual(u1["total_count"], 3)
            self.assertIsNotNone(u1["first_drop_at"])
            self.assertIsNotNone(u1["last_drop_at"])

            # Check User 2 stats
            u2 = await self.db.get_user_stats(102)
            self.assertIsNotNone(u2)
            self.assertEqual(u2["legendary_count"], 1)
            self.assertEqual(u2["total_count"], 1)

            # Check Non-existent user
            u3 = await self.db.get_user_stats(999)
            self.assertIsNone(u3)

            # Check Leaderboard
            top = await self.db.get_top_users(limit=10)
            self.assertEqual(len(top), 2)
            self.assertEqual(top[0]["user_id"], 101)  # 3 mishkas
            self.assertEqual(top[1]["user_id"], 102)  # 1 mishka

            # Check Global Stats
            global_stats = await self.db.get_bot_stats()
            self.assertEqual(global_stats["total_users"], 2)
            self.assertEqual(global_stats["total_mishkas"], 4)
            self.assertEqual(global_stats["common_total"], 2)
            self.assertEqual(global_stats["rare_total"], 1)
            self.assertEqual(global_stats["epic_total"], 0)
            self.assertEqual(global_stats["legendary_total"], 1)
        finally:
            await self.asyncTearDown()

    async def test_restart_persistence(self) -> None:
        await self.asyncSetUpself()
        try:
            # Write data
            await self.db.record_drop(
                user_id=555,
                first_name="Тест",
                rarity=MishkaRarity.EPIC,
            )
            # Recreate db client instance pointing to same file (simulating restart)
            new_db = Database(self.db_path)
            await new_db.init_db()

            u = await new_db.get_user_stats(555)
            self.assertIsNotNone(u)
            self.assertEqual(u["epic_count"], 1)
            self.assertEqual(u["total_count"], 1)
        finally:
            await self.asyncTearDown()


if __name__ == "__main__":
    unittest.main()

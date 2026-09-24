"""Integration tests for MishkaBot handlers and admin flows."""

import tempfile
import shutil
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.types import Chat, Message, User
from aiogram.filters import CommandObject

from config import Config
from database import Database
from handlers.commands import cmd_start, cmd_me, cmd_top, cmd_chance
from handlers.admin import cmd_set_chance, cmd_set_type, cmd_stats, cmd_reload
from handlers.messages import handle_group_message, _PROCESSED_SET, _PROCESSED_MESSAGES
from utils.mishka import MishkaRarity


class TestHandlersIntegration(unittest.IsolatedAsyncioTestCase):
    """Test handlers with mocked Telegram messages and real database/config."""

    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")
        self.env_path = Path(self.temp_dir) / ".env"
        self.env_path.write_text(
            "BOT_TOKEN=123:ABC\n"
            "MISHKA_CHANCE=5\n"
            "COMMON_MISHKA_CHANCE=70\n"
            "RARE_MISHKA_CHANCE=20\n"
            "EPIC_MISHKA_CHANCE=8\n"
            "LEGENDARY_MISHKA_CHANCE=2\n"
            f"DATABASE_PATH={self.db_path}\n",
            encoding="utf-8",
        )
        self.config = Config(
            bot_token="123:ABC",
            mishka_chance=5.0,
            common_chance=70.0,
            rare_chance=20.0,
            epic_chance=8.0,
            legendary_chance=2.0,
            database_path=self.db_path,
            spam_cooldown_seconds=0.0,  # disable cooldown for tests
            admin_ids={999},
        )
        self.database = Database(self.db_path)
        await self.database.init_db()
        _PROCESSED_SET.clear()
        _PROCESSED_MESSAGES.clear()

    async def asyncTearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_mock_message(
        self,
        text: str,
        user_id: int = 12345,
        first_name: str = "Иван",
        username: str = "ivan_user",
        is_bot: bool = False,
        chat_type: str = "supergroup",
        message_id: int = 1,
    ) -> MagicMock:
        msg = MagicMock(spec=Message)
        msg.message_id = message_id
        msg.text = text
        msg.from_user = MagicMock(spec=User)
        msg.from_user.id = user_id
        msg.from_user.first_name = first_name
        msg.from_user.username = username
        msg.from_user.last_name = None
        msg.from_user.is_bot = is_bot

        msg.chat = MagicMock(spec=Chat)
        msg.chat.id = -100123456789
        msg.chat.type = chat_type

        msg.answer = AsyncMock()
        msg.reply = AsyncMock()
        return msg

    async def test_cmd_start(self) -> None:
        msg = self.create_mock_message("/start")
        await cmd_start(msg, self.config)
        msg.answer.assert_called_once()
        self.assertIn("MishkaBot", msg.answer.call_args[0][0])

    async def test_cmd_me_empty_and_with_bears(self) -> None:
        msg = self.create_mock_message("/me", user_id=12345)
        # 1. When user has no bears
        await cmd_me(msg, self.database)
        msg.reply.assert_called_once()
        self.assertIn("У тебя пока нет мишек", msg.reply.call_args[0][0])

        # 2. Award some bears
        await self.database.record_drop(12345, "Иван", "ivan_user", rarity=MishkaRarity.COMMON)
        await self.database.record_drop(12345, "Иван", "ivan_user", rarity=MishkaRarity.EPIC)

        msg.reply.reset_mock()
        await cmd_me(msg, self.database)
        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]
        self.assertIn("Обычных: <b>1</b>", reply_text)
        self.assertIn("Эпических: <b>1</b>", reply_text)
        self.assertIn("Всего мишек: 2", reply_text)

    async def test_cmd_top(self) -> None:
        msg = self.create_mock_message("/top")
        # Empty leaderboard
        await cmd_top(msg, self.database)
        self.assertIn("Пока никто не нашел", msg.reply.call_args[0][0])

        # Add 2 users
        await self.database.record_drop(1, "User1", "u1", rarity=MishkaRarity.COMMON)
        await self.database.record_drop(1, "User1", "u1", rarity=MishkaRarity.COMMON)
        await self.database.record_drop(2, "User2", "u2", rarity=MishkaRarity.LEGENDARY)

        msg.reply.reset_mock()
        await cmd_top(msg, self.database)
        reply_text = msg.reply.call_args[0][0]
        self.assertIn("🥇 @u1 — <b>2</b> шт.", reply_text)
        self.assertIn("🥈 @u2 — <b>1</b> шт.", reply_text)

    async def test_cmd_chance(self) -> None:
        msg = self.create_mock_message("/chance")
        await cmd_chance(msg, self.config)
        msg.reply.assert_called_once()
        reply_text = msg.reply.call_args[0][0]
        self.assertIn("5%", reply_text)
        self.assertIn("70%", reply_text)

    async def test_admin_set_chance(self) -> None:
        msg = self.create_mock_message("/setchance 15", user_id=999)
        cmd_obj = CommandObject(prefix="/", command="setchance", args="15")

        with patch("handlers.admin.update_env_variable") as mock_update:
            await cmd_set_chance(msg, cmd_obj, self.config)
            self.assertEqual(self.config.mishka_chance, 15.0)
            mock_update.assert_called_once_with("MISHKA_CHANCE", "15")
            self.assertIn("успешно изменен на 15%", msg.reply.call_args[0][0])

    async def test_admin_set_type_valid_and_invalid(self) -> None:
        # Invalid sum (setting epic to 20 makes sum 70+20+20+2 = 112%)
        msg = self.create_mock_message("/settype epic 20", user_id=999)
        cmd_obj = CommandObject(prefix="/", command="settype", args="epic 20")
        await cmd_set_type(msg, cmd_obj, self.config)
        self.assertIn("Сумма вероятностей всех типов должна быть ровно 100%", msg.reply.call_args[0][0])
        self.assertEqual(self.config.epic_chance, 8.0)  # Unchanged

        # Valid sum adjustment: first set epic 10, then rare 18 -> sum 70 + 18 + 10 + 2 = 100%
        # Let's adjust epic to 10 when rare is 18:
        self.config.rare_chance = 18.0
        msg.reply.reset_mock()
        cmd_obj = CommandObject(prefix="/", command="settype", args="epic 10")
        with patch("handlers.admin.update_env_variable") as mock_update:
            await cmd_set_type(msg, cmd_obj, self.config)
            self.assertEqual(self.config.epic_chance, 10.0)
            mock_update.assert_called_once_with("EPIC_MISHKA_CHANCE", "10")
            self.assertIn("успешно изменена на <b>10%</b>", msg.reply.call_args[0][0])

    async def test_admin_stats(self) -> None:
        await self.database.increment_messages_processed(42)
        await self.database.record_drop(1, "Тест", rarity=MishkaRarity.RARE)
        msg = self.create_mock_message("/stats", user_id=999)
        await cmd_stats(msg, self.database)
        reply_text = msg.reply.call_args[0][0]
        self.assertIn("Обработано сообщений:</b> 42", reply_text)
        self.assertIn("Всего мишек выдано:</b> 1", reply_text)

    async def test_message_drop_and_bot_ignore(self) -> None:
        # 1. Message from bot is ignored
        bot_msg = self.create_mock_message("Привет", is_bot=True, message_id=101)
        await handle_group_message(bot_msg, self.database, self.config)
        bot_msg.reply.assert_not_called()

        # 2. Regular message with 100% chance awards mishka
        self.config.mishka_chance = 100.0
        user_msg = self.create_mock_message("Привет всем!", message_id=102)
        await handle_group_message(user_msg, self.database, self.config)
        user_msg.reply.assert_called_once()
        self.assertIn("Поздравляем!", user_msg.reply.call_args[0][0])

        # Check DB was updated
        user_stats = await self.database.get_user_stats(user_msg.from_user.id)
        self.assertEqual(user_stats["total_count"], 1)

        # 3. Duplicate message delivery is ignored
        user_msg.reply.reset_mock()
        await handle_group_message(user_msg, self.database, self.config)
        user_msg.reply.assert_not_called()
        # Count remains 1
        user_stats = await self.database.get_user_stats(user_msg.from_user.id)
        self.assertEqual(user_stats["total_count"], 1)


if __name__ == "__main__":
    unittest.main()

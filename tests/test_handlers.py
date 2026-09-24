"""Integration tests for Telegram Gifts & Stars bot handlers."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram.filters import CommandObject
from aiogram.types import Chat, Gift, Message, StarAmount, User

from config import Config
from database import Database
from handlers.admin import cmd_gifts, cmd_reload, cmd_set_chance, cmd_status, cmd_toggle_gift
from handlers.commands import cmd_chance, cmd_me, cmd_start, cmd_top
from handlers.messages import _PROCESSED_MESSAGES, _PROCESSED_SET, handle_group_message
from utils.gifts import gift_service


class TestHandlersIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")
        self.config = Config(
            bot_token="123:ABC",
            gift_drop_chance=5.0,
            target_chat_id=-100123456789,
            max_gift_price_stars=50,
            database_path=self.db_path,
            spam_cooldown_seconds=0.0,
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
        chat_id: int = -100123456789,
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
        msg.chat.id = chat_id
        msg.chat.title = "Тестовая группа"
        msg.chat.type = "supergroup"

        msg.answer = AsyncMock()
        msg.reply = AsyncMock()
        return msg

    async def test_cmd_start(self) -> None:
        msg = self.create_mock_message("/start")
        await cmd_start(msg, self.config)
        msg.answer.assert_called_once()
        self.assertIn("Telegram Gifts", msg.answer.call_args[0][0])

    async def test_cmd_me(self) -> None:
        msg = self.create_mock_message("/me", user_id=12345)
        # Empty
        await cmd_me(msg, self.database)
        self.assertIn("У вас пока нет выигранных подарков", msg.reply.call_args[0][0])

        # After winning
        await self.database.record_gift_delivery(
            user_id=12345,
            first_name="Иван",
            gift_id="star_gift",
            star_cost=25,
            status="SUCCESS",
        )
        msg.reply.reset_mock()
        await cmd_me(msg, self.database)
        self.assertIn("1 шт.", msg.reply.call_args[0][0])
        self.assertIn("25 ⭐", msg.reply.call_args[0][0])

    async def test_cmd_top(self) -> None:
        msg = self.create_mock_message("/top")
        await cmd_top(msg, self.database)
        self.assertIn("Пока никто в чате не выиграл подарки", msg.reply.call_args[0][0])

        await self.database.record_gift_delivery(
            user_id=1,
            first_name="Победитель",
            gift_id="star_gift",
            star_cost=100,
            status="SUCCESS",
        )
        msg.reply.reset_mock()
        await cmd_top(msg, self.database)
        self.assertIn("Победитель", msg.reply.call_args[0][0])

    async def test_admin_set_chance(self) -> None:
        msg = self.create_mock_message("/setchance 12.5")
        cmd_obj = CommandObject(prefix="/", command="setchance", args="12.5")

        with patch("handlers.admin.update_env_variable") as mock_update:
            await cmd_set_chance(msg, cmd_obj, self.config)
            self.assertEqual(self.config.gift_drop_chance, 12.5)
            mock_update.assert_called_once_with("GIFT_DROP_CHANCE", "12.5")
            self.assertIn("изменен на 12.5%", msg.reply.call_args[0][0])

    async def test_admin_gifts_and_toggle(self) -> None:
        bot = MagicMock()
        mock_gift = MagicMock(spec=Gift)
        mock_gift.id = "gift_teddy_1"
        mock_gift.star_count = 25
        mock_gift.remaining_count = 100

        with patch.object(gift_service, "get_available_gifts", return_value=[mock_gift]):
            msg = self.create_mock_message("/gifts")
            await cmd_gifts(msg, bot, self.config)
            self.assertIn("gift_teddy_1", msg.reply.call_args[0][0])

        # Test toggle gift
        msg_toggle = self.create_mock_message("/togglegift gift_teddy_1")
        cmd_obj = CommandObject(prefix="/", command="togglegift", args="gift_teddy_1")
        with patch("handlers.admin.update_env_variable"):
            await cmd_toggle_gift(msg_toggle, cmd_obj, self.config)
            self.assertIn("gift_teddy_1", self.config.enabled_gift_ids)

    async def test_admin_status(self) -> None:
        bot = MagicMock()
        bot.get_me = AsyncMock(return_value=MagicMock(username="mishka_test_bot"))
        bot.get_my_star_balance = AsyncMock(return_value=StarAmount(amount=250, nanostar_amount=0))
        bot.get_available_gifts = AsyncMock(return_value=MagicMock(gifts=[]))

        msg = self.create_mock_message("/status")
        await cmd_status(msg, bot, self.config, self.database)
        reply = msg.reply.call_args[0][0]
        self.assertIn("250 ⭐", reply)
        self.assertIn("mishka_test_bot", reply)

    async def test_group_message_handling(self) -> None:
        bot = MagicMock()
        bot.send_gift = AsyncMock(return_value=True)

        mock_gift = MagicMock(spec=Gift)
        mock_gift.id = "gift_777"
        mock_gift.star_count = 50

        # 1. Message from bot is ignored
        bot_msg = self.create_mock_message("bot text", is_bot=True, message_id=1)
        await handle_group_message(bot_msg, bot, self.database, self.config)
        bot_msg.reply.assert_not_called()

        # 2. Message from wrong group is ignored
        wrong_chat_msg = self.create_mock_message("hello", chat_id=-99999, message_id=2)
        await handle_group_message(wrong_chat_msg, bot, self.database, self.config)
        wrong_chat_msg.reply.assert_not_called()

        # 3. Winning roll sends real gift
        self.config.gift_drop_chance = 100.0
        with patch.object(
            gift_service, "select_gift_for_drop", return_value=(mock_gift, 200, "OK")
        ):
            with patch.object(gift_service, "send_real_gift", return_value=(True, None)):
                user_msg = self.create_mock_message("привет!", message_id=3)
                await handle_group_message(user_msg, bot, self.database, self.config)
                user_msg.reply.assert_called_once()
                self.assertIn("настоящий Telegram Gift", user_msg.reply.call_args[0][0])
                self.assertIn("50 ⭐", user_msg.reply.call_args[0][0])


if __name__ == "__main__":
    unittest.main()

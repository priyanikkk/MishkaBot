"""Group message listener for real Telegram Gift drops with rate-limiting and deduplication."""

import logging
import random
from collections import deque
from typing import Deque, Set
from aiogram import Bot, Router, F
from aiogram.types import Message

from config import Config
from database import Database
from utils.filters import ChatTypeFilter
from utils.gifts import gift_service
from utils.helpers import format_user_mention, is_rate_limited

logger = logging.getLogger(__name__)

router = Router(name="messages_router")
router.message.filter(ChatTypeFilter(["group", "supergroup"]))

_PROCESSED_MESSAGES: Deque[tuple] = deque(maxlen=2000)
_PROCESSED_SET: Set[tuple] = set()


def _is_duplicate_message(chat_id: int, message_id: int) -> bool:
    key = (chat_id, message_id)
    if key in _PROCESSED_SET:
        return True
    if len(_PROCESSED_MESSAGES) >= 2000:
        oldest = _PROCESSED_MESSAGES.popleft()
        _PROCESSED_SET.discard(oldest)
    _PROCESSED_MESSAGES.append(key)
    _PROCESSED_SET.add(key)
    return False


@router.message(
    ~F.text.startswith("/"),
    ~F.from_user.is_bot,
)
async def handle_group_message(
    message: Message, bot: Bot, database: Database, config: Config
) -> None:
    """
    Process regular messages:
    1. Filter out bots and duplicate updates.
    2. Enforce target group check if TARGET_CHAT_ID is configured.
    3. Update global messages counter.
    4. Enforce anti-spam cooldown per user.
    5. Roll drop chance.
    6. If won: pick real gift, pay with Telegram Stars via Bot API, and deliver to user profile.
    """
    if not message.from_user:
        return

    chat_id = message.chat.id
    message_id = message.message_id
    user = message.from_user

    # Filter target group if specified
    if config.target_chat_id and chat_id != config.target_chat_id:
        return

    # Check update deduplication
    if _is_duplicate_message(chat_id, message_id):
        return

    # Count message in stats
    await database.increment_messages_processed(1)

    # Check anti-spam cooldown
    if is_rate_limited(user.id, config.spam_cooldown_seconds):
        return

    # Roll drop chance
    if config.gift_drop_chance <= 0.0:
        return

    roll = random.uniform(0.0, 100.0)
    if roll > config.gift_drop_chance:
        return

    # User won a gift drop! Select real gift from catalog
    gift, balance, status = await gift_service.select_gift_for_drop(bot, config)

    if not gift:
        logger.warning(
            "Gift drop triggered for user %s, but no gift could be sent: %s (Balance: %d Stars)",
            user.id,
            status,
            balance,
        )
        if status == "INSUFFICIENT_BALANCE":
            logger.error("ALERT: Bot has 0 Stars balance! Please top up bot Stars to send gifts.")
        return

    # Send real gift via Telegram Bot API
    chat_title = message.chat.title or "чат"
    congrats_note = f"Подарок за активность в {chat_title}! ⭐"

    success, error_msg = await gift_service.send_real_gift(
        bot=bot,
        user_id=user.id,
        gift_id=gift.id,
        text=congrats_note,
    )

    if success:
        # Record in database
        await database.record_gift_delivery(
            user_id=user.id,
            first_name=user.first_name,
            gift_id=gift.id,
            star_cost=gift.star_count,
            status="SUCCESS",
            username=user.username,
            last_name=user.last_name,
        )

        mention = format_user_mention(user.id, user.first_name, user.username)
        announcement = (
            f"🎉 <b>ПОЗДРАВЛЯЕМ!</b> {mention} только что выиграл(а) "
            f"<b>настоящий Telegram Gift</b> стоимостью <b>{gift.star_count} ⭐</b>!\n"
            "🎁 Подарок уже отправлен в ваш профиль Telegram!"
        )

        try:
            await message.reply(announcement, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to send chat announcement: %s", e)
    else:
        # Record failed delivery attempt
        await database.record_gift_delivery(
            user_id=user.id,
            first_name=user.first_name,
            gift_id=gift.id,
            star_cost=gift.star_count,
            status="FAILED",
            username=user.username,
            last_name=user.last_name,
            error_message=error_msg,
        )
        logger.error("Gift delivery to user %s failed: %s", user.id, error_msg)

"""Message handler for group chats: RNG mishka drop, rate limiting, and stats tracking."""

import logging
from collections import deque
from typing import Deque, Set
from aiogram import Router, F
from aiogram.types import Message

from config import Config
from database import Database
from utils.filters import ChatTypeFilter
from utils.helpers import format_user_mention, is_rate_limited
from utils.mishka import roll_mishka_drop

logger = logging.getLogger(__name__)

router = Router(name="messages_router")

# Only process messages in groups and supergroups
router.message.filter(ChatTypeFilter(["group", "supergroup"]))

# Deduplication ring buffer for Telegram update replays (chat_id, message_id)
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
async def handle_group_message(message: Message, database: Database, config: Config) -> None:
    """
    Process regular messages in Telegram groups:
    1. Verify user is not a bot.
    2. Check message deduplication.
    3. Update global messages processed counter.
    4. Enforce anti-spam cooldown per user.
    5. Roll drop chance and award mishka if won.
    """
    if not message.from_user:
        return

    chat_id = message.chat.id
    message_id = message.message_id
    user = message.from_user

    # Prevent processing duplicate update deliveries
    if _is_duplicate_message(chat_id, message_id):
        return

    # Count every valid user message in global bot stats
    await database.increment_messages_processed(1)

    # Anti-spam: enforce cooldown between reward-eligible messages for the user
    if is_rate_limited(user.id, config.spam_cooldown_seconds):
        return

    # Roll drop chance
    dropped, mishka_info = roll_mishka_drop(
        base_chance=config.mishka_chance,
        common_chance=config.common_chance,
        rare_chance=config.rare_chance,
        epic_chance=config.epic_chance,
        legendary_chance=config.legendary_chance,
    )

    if not dropped or not mishka_info:
        return

    # Award mishka in database
    await database.record_drop(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
        last_name=user.last_name,
        rarity=mishka_info.rarity,
    )

    mention = format_user_mention(
        user_id=user.id,
        first_name=user.first_name,
        username=user.username,
    )

    congrats_text = (
        f"🐻 <b>Поздравляем! {mention} получил {mishka_info.emoji} {mishka_info.accusative_name}!</b>"
    )

    try:
        await message.reply(congrats_text, parse_mode="HTML")
        logger.info(
            "User %s (%s) won %s in chat %s",
            user.id,
            user.username,
            mishka_info.rarity.value,
            chat_id,
        )
    except Exception as e:
        logger.error("Failed to send reward message: %s", e)

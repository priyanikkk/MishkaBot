"""Telegram Gifts and Stars service module using official Telegram Bot API."""

import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from aiogram import Bot
from aiogram.types import Gift, Gifts, StarAmount

from config import Config

logger = logging.getLogger(__name__)


class GiftService:
    def __init__(self) -> None:
        self._cached_gifts: List[Gift] = []
        self._last_catalog_fetch: float = 0.0
        self._cache_ttl_seconds: float = 300.0  # 5 minutes catalog cache

    async def get_available_gifts(self, bot: Bot, force_refresh: bool = False) -> List[Gift]:
        """
        Fetch real Telegram Gifts catalog from official Telegram Bot API.
        Uses in-memory caching to avoid hitting Telegram API on every message.
        """
        now = time.monotonic()
        if not force_refresh and self._cached_gifts and (now - self._last_catalog_fetch < self._cache_ttl_seconds):
            return self._cached_gifts

        try:
            gifts_obj: Gifts = await bot.get_available_gifts()
            self._cached_gifts = gifts_obj.gifts if gifts_obj and gifts_obj.gifts else []
            self._last_catalog_fetch = now
            logger.info("Loaded %d real Telegram gifts from API", len(self._cached_gifts))
            return self._cached_gifts
        except Exception as e:
            logger.error("Failed to fetch available gifts from Telegram API: %s", e)
            if self._cached_gifts:
                return self._cached_gifts
            return []

    async def get_star_balance(self, bot: Bot) -> int:
        """
        Fetch the current official Telegram Stars balance of the bot.
        """
        try:
            amount: StarAmount = await bot.get_my_star_balance()
            return amount.amount if amount else 0
        except Exception as e:
            logger.error("Failed to fetch bot star balance: %s", e)
            return 0

    async def select_gift_for_drop(
        self, bot: Bot, config: Config
    ) -> Tuple[Optional[Gift], int, str]:
        """
        Select an eligible real Telegram Gift according to:
        1. Current bot Stars balance;
        2. Configured enabled gift IDs;
        3. Configured MAX_GIFT_PRICE_STARS;
        4. Availability / remaining count.
        
        Returns:
            (selected_gift, current_star_balance, status_message)
        """
        balance = await self.get_star_balance(bot)
        if balance <= 0:
            return None, balance, "INSUFFICIENT_BALANCE"

        all_gifts = await self.get_available_gifts(bot)
        if not all_gifts:
            return None, balance, "NO_GIFTS_AVAILABLE"

        eligible_gifts: List[Gift] = []
        for g in all_gifts:
            # Check remaining supply if it's a limited gift
            if g.remaining_count is not None and g.remaining_count <= 0:
                continue

            # Check if gift is in enabled filter (if filter specified)
            if config.enabled_gift_ids and g.id not in config.enabled_gift_ids:
                continue

            # Check max price limit
            if config.max_gift_price_stars > 0 and g.star_count > config.max_gift_price_stars:
                continue

            # Check affordability
            if g.star_count > balance:
                continue

            eligible_gifts.append(g)

        if not eligible_gifts:
            return None, balance, "NO_ELIGIBLE_GIFTS"

        selected = random.choice(eligible_gifts)
        return selected, balance, "OK"

    async def send_real_gift(
        self,
        bot: Bot,
        user_id: int,
        gift_id: str,
        text: Optional[str] = "Поздравляем с победой в чате! ⭐",
    ) -> Tuple[bool, Optional[str]]:
        """
        Send a real Telegram Gift to the recipient via official Bot API.
        The stars are debited directly from the bot's Telegram Stars balance.
        """
        safe_text = (text[:128]) if text else None
        try:
            result = await bot.send_gift(
                user_id=user_id,
                gift_id=gift_id,
                text=safe_text,
            )
            logger.info("Successfully sent real gift %s to user %s", gift_id, user_id)
            return True, None
        except Exception as e:
            err_msg = str(e)
            logger.error("Failed to send gift %s to user %s: %s", gift_id, user_id, err_msg)
            return False, err_msg


# Global service singleton
gift_service = GiftService()

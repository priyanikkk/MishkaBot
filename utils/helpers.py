"""Helper functions for formatting, user mentions, and anti-spam protection."""

import html
import time
from typing import Dict, Optional

# In-memory debounce cache: user_id -> monotonic timestamp
_USER_LAST_ACTIVITY: Dict[int, float] = {}
_LAST_CLEANUP: float = time.monotonic()


def is_rate_limited(user_id: int, cooldown_seconds: float = 3.0) -> bool:
    """
    Checks if a user is sending messages too quickly to be eligible for rewards.
    Returns True if rate limited (skip reward check), False otherwise.
    """
    global _LAST_CLEANUP
    now = time.monotonic()

    # Periodic cleanup every 5 minutes to prevent memory accumulation
    if now - _LAST_CLEANUP > 300.0:
        cutoff = now - 60.0
        keys_to_delete = [uid for uid, ts in _USER_LAST_ACTIVITY.items() if ts < cutoff]
        for uid in keys_to_delete:
            _USER_LAST_ACTIVITY.pop(uid, None)
        _LAST_CLEANUP = now

    last_time = _USER_LAST_ACTIVITY.get(user_id)
    if last_time is not None and (now - last_time) < cooldown_seconds:
        return True

    _USER_LAST_ACTIVITY[user_id] = now
    return False


def escape_html(text: Optional[str]) -> str:
    """Safely escape text for Telegram HTML parse mode."""
    if not text:
        return ""
    return html.escape(str(text))


def format_user_mention(user_id: int, first_name: str, username: Optional[str] = None) -> str:
    """
    Format user mention nicely for Telegram.
    Uses @username if available, otherwise HTML user profile link.
    """
    if username:
        # Strip leading @ if present
        clean_username = username.lstrip("@")
        return f"@{escape_html(clean_username)}"
    
    safe_name = escape_html(first_name) or f"Пользователь {user_id}"
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'

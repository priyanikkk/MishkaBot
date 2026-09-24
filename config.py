"""Configuration management for Telegram Gifts & Stars Bot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Set
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class Config:
    bot_token: str
    gift_drop_chance: float = 5.0
    target_chat_id: Optional[int] = None
    enabled_gift_ids: Set[str] = field(default_factory=set)
    max_gift_price_stars: int = 0  # 0 means no price cap
    telegram_api_id: Optional[int] = None
    telegram_api_hash: Optional[str] = None
    telegram_phone: Optional[str] = None
    session_name: str = "secrets/user_session"
    stars_source: str = "bot"  # 'bot' or 'user_session'
    database_path: str = "data/bot.db"
    spam_cooldown_seconds: float = 3.0
    admin_ids: Set[int] = field(default_factory=set)

    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.bot_token:
            raise ConfigValidationError(
                "BOT_TOKEN не задан! Укажите токен бота в файле .env или переменной окружения."
            )

        if not (0.0 <= self.gift_drop_chance <= 100.0):
            raise ConfigValidationError(
                f"GIFT_DROP_CHANCE должен быть в диапазоне от 0 до 100! Текущее значение: {self.gift_drop_chance}"
            )

        if self.stars_source not in ("bot", "user_session"):
            raise ConfigValidationError(
                f"STARS_SOURCE должен быть 'bot' или 'user_session'! Получено: {self.stars_source}"
            )

        if self.stars_source == "user_session" and (not self.telegram_api_id or not self.telegram_api_hash):
            raise ConfigValidationError(
                "При STARS_SOURCE=user_session необходимо указать TELEGRAM_API_ID и TELEGRAM_API_HASH!"
            )


def parse_id_set(raw_value: str) -> Set[int]:
    """Parse comma-separated integer IDs string."""
    result: Set[int] = set()
    if not raw_value:
        return result
    for part in raw_value.split(","):
        cleaned = part.strip()
        # Handle negative chat IDs (e.g. -100123456789)
        if cleaned.lstrip("-").isdigit():
            result.add(int(cleaned))
    return result


def parse_string_set(raw_value: str) -> Set[str]:
    """Parse comma-separated string IDs."""
    result: Set[str] = set()
    if not raw_value:
        return result
    for part in raw_value.split(","):
        cleaned = part.strip()
        if cleaned:
            result.add(cleaned)
    return result


def load_config(env_file: Path | str | None = None) -> Config:
    """Load and validate configuration from environment and .env file."""
    path = Path(env_file) if env_file else ENV_PATH
    if path.exists():
        load_dotenv(dotenv_path=path, override=True)
    else:
        load_dotenv(override=True)

    bot_token = os.getenv("BOT_TOKEN", "").strip()

    try:
        gift_drop_chance = float(os.getenv("GIFT_DROP_CHANCE", "5.0"))
    except ValueError:
        gift_drop_chance = 5.0

    target_chat_raw = os.getenv("TARGET_CHAT_ID", "").strip()
    target_chat_id: Optional[int] = None
    if target_chat_raw and target_chat_raw.lstrip("-").isdigit():
        target_chat_id = int(target_chat_raw)

    enabled_gift_ids = parse_string_set(os.getenv("ENABLED_GIFT_IDS", ""))

    try:
        max_gift_price_stars = int(os.getenv("MAX_GIFT_PRICE_STARS", "0"))
    except ValueError:
        max_gift_price_stars = 0

    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_id = int(api_id_raw) if api_id_raw.isdigit() else None
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip() or None
    phone = os.getenv("TELEGRAM_PHONE", "").strip() or None
    session_name = os.getenv("SESSION_NAME", "secrets/user_session").strip()
    stars_source = os.getenv("STARS_SOURCE", "bot").strip().lower()

    database_path = os.getenv("DATABASE_PATH", "data/bot.db").strip()

    try:
        spam_cooldown = float(os.getenv("SPAM_COOLDOWN_SECONDS", "3.0"))
    except ValueError:
        spam_cooldown = 3.0

    admin_ids = parse_id_set(os.getenv("ADMIN_IDS", ""))

    cfg = Config(
        bot_token=bot_token,
        gift_drop_chance=gift_drop_chance,
        target_chat_id=target_chat_id,
        enabled_gift_ids=enabled_gift_ids,
        max_gift_price_stars=max_gift_price_stars,
        telegram_api_id=api_id,
        telegram_api_hash=api_hash,
        telegram_phone=phone,
        session_name=session_name,
        stars_source=stars_source,
        database_path=database_path,
        spam_cooldown_seconds=spam_cooldown,
        admin_ids=admin_ids,
    )
    cfg.validate()
    return cfg


def update_env_variable(key: str, value: Any, env_file: Path | str | None = None) -> None:
    """Safely update or add an environment variable in the .env file."""
    path = Path(env_file) if env_file else ENV_PATH
    key_str = str(key).strip()
    val_str = str(value).strip()

    lines = []
    found = False

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key_str}=") or stripped.startswith(f"{key_str} ="):
            new_lines.append(f"{key_str}={val_str}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key_str}={val_str}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    os.environ[key_str] = val_str

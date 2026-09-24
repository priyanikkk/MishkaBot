"""Configuration management for MishkaBot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class Config:
    bot_token: str
    mishka_chance: float
    common_chance: float
    rare_chance: float
    epic_chance: float
    legendary_chance: float
    database_path: str
    spam_cooldown_seconds: float = 3.0
    admin_ids: Set[int] = field(default_factory=set)

    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.bot_token:
            raise ConfigValidationError(
                "BOT_TOKEN не задан! Укажите токен бота в файле .env или переменной окружения BOT_TOKEN."
            )

        if not (0.0 <= self.mishka_chance <= 100.0):
            raise ConfigValidationError(
                f"MISHKA_CHANCE должен быть в диапазоне от 0 до 100! Текущее значение: {self.mishka_chance}"
            )

        types_sum = round(
            self.common_chance + self.rare_chance + self.epic_chance + self.legendary_chance, 4
        )
        if types_sum != 100.0:
            raise ConfigValidationError(
                f"Ошибка конфигурации! Сумма вероятностей типов мишек должна быть ровно 100%. "
                f"Текущая сумма: {types_sum}% ("
                f"Обычный: {self.common_chance}%, "
                f"Редкий: {self.rare_chance}%, "
                f"Эпический: {self.epic_chance}%, "
                f"Легендарный: {self.legendary_chance}%)"
            )

        for name, val in [
            ("COMMON_MISHKA_CHANCE", self.common_chance),
            ("RARE_MISHKA_CHANCE", self.rare_chance),
            ("EPIC_MISHKA_CHANCE", self.epic_chance),
            ("LEGENDARY_MISHKA_CHANCE", self.legendary_chance),
        ]:
            if not (0.0 <= val <= 100.0):
                raise ConfigValidationError(
                    f"{name} должен быть в диапазоне от 0 до 100! Текущее значение: {val}"
                )


def parse_admin_ids(raw_value: str) -> Set[int]:
    """Parse comma-separated admin IDs string."""
    ids: Set[int] = set()
    if not raw_value:
        return ids
    for part in raw_value.split(","):
        cleaned = part.strip()
        if cleaned.isdigit():
            ids.add(int(cleaned))
    return ids


def load_config(env_file: Path | str | None = None) -> Config:
    """Load and validate configuration from environment and .env file."""
    path = Path(env_file) if env_file else ENV_PATH
    if path.exists():
        load_dotenv(dotenv_path=path, override=True)
    else:
        # Fallback to system environment
        load_dotenv(override=True)

    bot_token = os.getenv("BOT_TOKEN", "").strip()

    try:
        mishka_chance = float(os.getenv("MISHKA_CHANCE", "5"))
    except ValueError:
        mishka_chance = 5.0

    try:
        common_chance = float(os.getenv("COMMON_MISHKA_CHANCE", "70"))
        rare_chance = float(os.getenv("RARE_MISHKA_CHANCE", "20"))
        epic_chance = float(os.getenv("EPIC_MISHKA_CHANCE", "8"))
        legendary_chance = float(os.getenv("LEGENDARY_MISHKA_CHANCE", "2"))
    except ValueError as e:
        raise ConfigValidationError(f"Некорректное числовое значение в шансах мишек: {e}")

    database_path = os.getenv("DATABASE_PATH", "data/mishka.db").strip()

    try:
        spam_cooldown = float(os.getenv("SPAM_COOLDOWN_SECONDS", "3.0"))
    except ValueError:
        spam_cooldown = 3.0

    admin_ids = parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    cfg = Config(
        bot_token=bot_token,
        mishka_chance=mishka_chance,
        common_chance=common_chance,
        rare_chance=rare_chance,
        epic_chance=epic_chance,
        legendary_chance=legendary_chance,
        database_path=database_path,
        spam_cooldown_seconds=spam_cooldown,
        admin_ids=admin_ids,
    )
    cfg.validate()
    return cfg


def update_env_variable(key: str, value: str | int | float, env_file: Path | str | None = None) -> None:
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

    # Also update in current process environment
    os.environ[key_str] = val_str

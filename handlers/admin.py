"""Admin commands handler: /setchance, /settype, /stats, /reload."""

import logging
from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import Config, load_config, update_env_variable, ConfigValidationError
from database import Database
from utils.filters import AdminFilter
from utils.mishka import (
    MishkaRarity,
    MISHKA_TYPES,
    parse_rarity,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_router")
# Apply AdminFilter to all messages in this router
router.message.filter(AdminFilter())


@router.message(Command("setchance"))
async def cmd_set_chance(message: Message, command: CommandObject, config: Config) -> None:
    """
    Handle /setchance <percent>
    Example: /setchance 5
    """
    args = command.args
    if not args:
        await message.reply(
            "ℹ️ <b>Использование:</b> <code>/setchance &lt;процент&gt;</code>\n"
            f"Текущий общий шанс: <b>{config.mishka_chance:g}%</b>\n\n"
            "<i>Пример:</i> <code>/setchance 5</code>",
            parse_mode="HTML",
        )
        return

    try:
        new_chance = float(args.replace(",", ".").strip())
    except ValueError:
        await message.reply(
            "❌ Некорректное число! Укажите число от 0 до 100.\n<i>Пример:</i> <code>/setchance 7.5</code>",
            parse_mode="HTML",
        )
        return

    if not (0.0 <= new_chance <= 100.0):
        await message.reply(
            "❌ Шанс должен быть в диапазоне от <b>0</b> до <b>100%</b>!",
            parse_mode="HTML",
        )
        return

    # Update in-memory config and persist to .env
    config.mishka_chance = new_chance
    update_env_variable("MISHKA_CHANCE", f"{new_chance:g}")

    logger.info("Admin %s updated MISHKA_CHANCE to %s%%", message.from_user.id, new_chance)
    await message.reply(
        f"✅ <b>Общий шанс выпадения мишки успешно изменен на {new_chance:g}%!</b>\n"
        "Настройка сохранена в <code>.env</code> и будет действовать после перезапуска.",
        parse_mode="HTML",
    )


@router.message(Command("settype"))
async def cmd_set_type(message: Message, command: CommandObject, config: Config) -> None:
    """
    Handle /settype <type> <percentage>
    Example: /settype common 70
    """
    args = (command.args or "").split()
    if len(args) != 2:
        await message.reply(
            "ℹ️ <b>Использование:</b> <code>/settype &lt;тип&gt; &lt;процент&gt;</code>\n\n"
            "<b>Допустимые типы:</b>\n"
            f"• <code>common</code> (текущий: {config.common_chance:g}%)\n"
            f"• <code>rare</code> (текущий: {config.rare_chance:g}%)\n"
            f"• <code>epic</code> (текущий: {config.epic_chance:g}%)\n"
            f"• <code>legendary</code> (текущий: {config.legendary_chance:g}%)\n\n"
            "<i>Пример:</i> <code>/settype common 70</code>",
            parse_mode="HTML",
        )
        return

    type_raw, percent_raw = args[0], args[1]
    rarity = parse_rarity(type_raw)
    if not rarity:
        await message.reply(
            f"❌ Неизвестный тип мишки: <code>{type_raw}</code>!\n"
            "Доступные варианты: <code>common</code>, <code>rare</code>, <code>epic</code>, <code>legendary</code>.",
            parse_mode="HTML",
        )
        return

    try:
        new_val = float(percent_raw.replace(",", ".").strip())
    except ValueError:
        await message.reply(
            "❌ Некорректный процент! Укажите число от 0 до 100.",
            parse_mode="HTML",
        )
        return

    if not (0.0 <= new_val <= 100.0):
        await message.reply(
            "❌ Процент должен быть в диапазоне от 0 до 100!",
            parse_mode="HTML",
        )
        return

    # Calculate test sum before applying
    c = new_val if rarity == MishkaRarity.COMMON else config.common_chance
    r = new_val if rarity == MishkaRarity.RARE else config.rare_chance
    e = new_val if rarity == MishkaRarity.EPIC else config.epic_chance
    l = new_val if rarity == MishkaRarity.LEGENDARY else config.legendary_chance

    test_sum = round(c + r + e + l, 4)
    if test_sum != 100.0:
        await message.reply(
            "❌ <b>Ошибка: Сумма вероятностей всех типов должна быть ровно 100%!</b>\n\n"
            f"С этим изменением сумма составила бы: <b>{test_sum:g}%</b>\n\n"
            "<b>Текущие значения:</b>\n"
            f"• 🧸 common: {config.common_chance:g}%\n"
            f"• 🐻 rare: {config.rare_chance:g}%\n"
            f"• 🐼 epic: {config.epic_chance:g}%\n"
            f"• 🐨 legendary: {config.legendary_chance:g}%\n\n"
            "<i>Скорректируйте остальные типы, чтобы суммарно получилось ровно 100%.</i>",
            parse_mode="HTML",
        )
        return

    # Apply changes
    env_keys = {
        MishkaRarity.COMMON: "COMMON_MISHKA_CHANCE",
        MishkaRarity.RARE: "RARE_MISHKA_CHANCE",
        MishkaRarity.EPIC: "EPIC_MISHKA_CHANCE",
        MishkaRarity.LEGENDARY: "LEGENDARY_MISHKA_CHANCE",
    }

    if rarity == MishkaRarity.COMMON:
        config.common_chance = new_val
    elif rarity == MishkaRarity.RARE:
        config.rare_chance = new_val
    elif rarity == MishkaRarity.EPIC:
        config.epic_chance = new_val
    elif rarity == MishkaRarity.LEGENDARY:
        config.legendary_chance = new_val

    update_env_variable(env_keys[rarity], f"{new_val:g}")

    info = MISHKA_TYPES[rarity]
    logger.info("Admin %s updated %s to %s%%", message.from_user.id, env_keys[rarity], new_val)
    await message.reply(
        f"✅ Вероятность для <b>{info.emoji} {info.name}</b> успешно изменена на <b>{new_val:g}%</b>!\n"
        f"Сумма всех типов: <b>100%</b>.\n"
        "Настройка сохранена в <code>.env</code>.",
        parse_mode="HTML",
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message, database: Database) -> None:
    """Handle /stats command — show global bot metrics."""
    stats = await database.get_bot_stats()

    msg_count = stats.get("messages_processed", 0)
    total_drops = stats.get("total_mishkas", 0)
    users_count = stats.get("total_users", 0)
    common_c = stats.get("common_total", 0)
    rare_c = stats.get("rare_total", 0)
    epic_c = stats.get("epic_total", 0)
    legend_c = stats.get("legendary_total", 0)

    drop_ratio = (total_drops / msg_count * 100) if msg_count > 0 else 0.0

    text = (
        "📊 <b>Глобальная статистика MishkaBot:</b>\n\n"
        f"💬 <b>Обработано сообщений:</b> {msg_count:,}\n"
        f"🎁 <b>Всего мишек выдано:</b> {total_drops:,} ({drop_ratio:.2f}% от сообщений)\n"
        f"👥 <b>Пользователей с мишками:</b> {users_count:,}\n\n"
        "<b>Количество выданных по типам:</b>\n"
        f"🧸 Обычных: <b>{common_c:,}</b>\n"
        f"🐻 Редких: <b>{rare_c:,}</b>\n"
        f"🐼 Эпических: <b>{epic_c:,}</b>\n"
        f"🐨 Легендарных: <b>{legend_c:,}</b>"
    )
    await message.reply(text, parse_mode="HTML")


@router.message(Command("reload"))
async def cmd_reload(message: Message, config: Config) -> None:
    """Handle /reload command — reload settings from .env."""
    try:
        new_config = load_config()
        # Copy attributes into existing config object
        config.mishka_chance = new_config.mishka_chance
        config.common_chance = new_config.common_chance
        config.rare_chance = new_config.rare_chance
        config.epic_chance = new_config.epic_chance
        config.legendary_chance = new_config.legendary_chance
        config.database_path = new_config.database_path
        config.spam_cooldown_seconds = new_config.spam_cooldown_seconds
        config.admin_ids = new_config.admin_ids

        logger.info("Config successfully reloaded by admin %s", message.from_user.id)
        await message.reply(
            "🔄 <b>Настройки успешно перезагружены из <code>.env</code>!</b>\n\n"
            f"• Общий шанс: <b>{config.mishka_chance:g}%</b>\n"
            f"• Обычный: <b>{config.common_chance:g}%</b>\n"
            f"• Редкий: <b>{config.rare_chance:g}%</b>\n"
            f"• Эпический: <b>{config.epic_chance:g}%</b>\n"
            f"• Легендарный: <b>{config.legendary_chance:g}%</b>",
            parse_mode="HTML",
        )
    except ConfigValidationError as e:
        logger.error("Failed to reload config: %s", e)
        await message.reply(
            f"❌ <b>Ошибка валидации при перезагрузке:</b>\n{e}\n\n"
            "Старые настройки остались активными.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Unexpected error reloading config")
        await message.reply(
            f"❌ Непредвиденная ошибка при перезагрузке: <code>{e}</code>",
            parse_mode="HTML",
        )

"""Admin commands handler: /setchance, /gifts, /togglegift, /status, /reload."""

import logging
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import Config, load_config, update_env_variable, ConfigValidationError
from database import Database
from utils.filters import AdminFilter
from utils.gifts import gift_service
from utils.mtproto import MTProtoSessionManager

logger = logging.getLogger(__name__)

router = Router(name="admin_router")
router.message.filter(AdminFilter())


@router.message(Command("setchance"))
async def cmd_set_chance(message: Message, command: CommandObject, config: Config) -> None:
    """Handle /setchance <percent>."""
    args = command.args
    if not args:
        await message.reply(
            "ℹ️ <b>Использование:</b> <code>/setchance &lt;процент&gt;</code>\n"
            f"Текущий шанс: <b>{config.gift_drop_chance:g}%</b>\n\n"
            "<i>Пример:</i> <code>/setchance 5</code> (означает 5% на каждое сообщение)",
            parse_mode="HTML",
        )
        return

    try:
        new_chance = float(args.replace(",", ".").strip())
    except ValueError:
        await message.reply(
            "❌ Некорректное число! Укажите процент от 0 до 100.",
            parse_mode="HTML",
        )
        return

    if not (0.0 <= new_chance <= 100.0):
        await message.reply(
            "❌ Шанс должен быть в диапазоне от 0 до 100%!",
            parse_mode="HTML",
        )
        return

    config.gift_drop_chance = new_chance
    update_env_variable("GIFT_DROP_CHANCE", f"{new_chance:g}")

    logger.info("Admin %s updated GIFT_DROP_CHANCE to %s%%", message.from_user.id, new_chance)
    await message.reply(
        f"✅ <b>Шанс выпадения реального подарка изменен на {new_chance:g}%!</b>\n"
        "Настройка сохранена в <code>.env</code>.",
        parse_mode="HTML",
    )


@router.message(Command("gifts"))
async def cmd_gifts(message: Message, bot: Bot, config: Config) -> None:
    """Handle /gifts command — display real Telegram Gifts from Telegram API."""
    await message.reply("⏳ Загружаю актуальный каталог подарков из Telegram API...")

    gifts = await gift_service.get_available_gifts(bot, force_refresh=True)
    if not gifts:
        await message.reply(
            "⚠️ В данный момент Telegram API не вернул доступных подарков "
            "или метод временно недоступен.",
            parse_mode="HTML",
        )
        return

    lines = [
        f"🎁 <b>Актуальные подарки Telegram ({len(gifts)} шт.):</b>\n",
        "<i>Для включения/выключения используйте:</i> <code>/togglegift &lt;ID&gt;</code>\n",
    ]

    for g in gifts[:15]:  # Display up to 15 to fit message limits
        is_enabled = (not config.enabled_gift_ids) or (g.id in config.enabled_gift_ids)
        status_emoji = "✅" if is_enabled else "❌"

        rem_text = (
            f"осталось {g.remaining_count:,}"
            if g.remaining_count is not None
            else "неограниченно"
        )
        lines.append(
            f"{status_emoji} <b>ID:</b> <code>{g.id}</code> | <b>{g.star_count} ⭐</b> | {rem_text}"
        )

    if len(gifts) > 15:
        lines.append(f"\n<i>... и еще {len(gifts) - 15} подарков в каталоге.</i>")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("togglegift"))
async def cmd_toggle_gift(message: Message, command: CommandObject, config: Config) -> None:
    """Handle /togglegift <gift_id> — toggle a specific gift in the drop pool."""
    gift_id = (command.args or "").strip()
    if not gift_id:
        await message.reply(
            "ℹ️ <b>Использование:</b> <code>/togglegift &lt;ID_подарка&gt;</code>\n"
            "Список доступных ID смотрите в команде <code>/gifts</code>.",
            parse_mode="HTML",
        )
        return

    if gift_id in config.enabled_gift_ids:
        config.enabled_gift_ids.remove(gift_id)
        action_text = "отключен из пула выпадения ❌"
    else:
        config.enabled_gift_ids.add(gift_id)
        action_text = "добавлен в пул выпадения ✅"

    # Persist back to .env
    new_val = ",".join(sorted(config.enabled_gift_ids))
    update_env_variable("ENABLED_GIFT_IDS", new_val)

    await message.reply(
        f"🎁 Подарок <code>{gift_id}</code> теперь <b>{action_text}</b>.\n"
        f"Всего выбрано подарков: <b>{len(config.enabled_gift_ids)}</b> (если 0 — разрешены все).",
        parse_mode="HTML",
    )


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot, config: Config, database: Database) -> None:
    """Handle /status command — comprehensive live diagnostics."""
    # 1. Telegram Bot connection
    try:
        bot_user = await bot.get_me()
        bot_status = f"✅ Подключен (@{bot_user.username})"
    except Exception as e:
        bot_status = f"❌ Ошибка: {e}"

    # 2. MTProto session status
    session_mgr = MTProtoSessionManager(config)
    is_session_auth, session_details = await session_mgr.check_session_status()
    session_status = (
        f"✅ Авторизован ({session_details})"
        if is_session_auth
        else f"ℹ️ {session_details}"
    )

    # 3. Telegram Stars balance
    star_balance = await gift_service.get_star_balance(bot)

    # 4. Available gifts and affordability
    gifts = await gift_service.get_available_gifts(bot)
    min_gift_price = min([g.star_count for g in gifts]) if gifts else 0
    can_send_gifts = (star_balance >= min_gift_price) and (len(gifts) > 0)
    gifts_status = (
        f"✅ Доступна (Мин. цена: {min_gift_price} ⭐)"
        if can_send_gifts
        else f"⚠️ Недостаточно Stars (Мин. нужно: {min_gift_price} ⭐)"
    )

    # 5. Global gift deliveries metrics
    stats = await database.get_global_gift_stats()

    # 6. Target Group
    target_chat_info = (
        f"<code>{config.target_chat_id}</code>"
        if config.target_chat_id
        else "Любая группа, где бот состоит"
    )

    # 7. Enabled gifts info
    enabled_info = (
        f"{len(config.enabled_gift_ids)} конкретных ID"
        if config.enabled_gift_ids
        else "Все доступные в каталоге"
    )

    text = (
        "📊 <b>Статус системы Telegram Gifts & Stars:</b>\n\n"
        f"🤖 <b>Telegram Bot API:</b> {bot_status}\n"
        f"📱 <b>Пользовательская сессия:</b> {session_status}\n"
        f"⭐ <b>Текущий баланс Stars бота:</b> <b>{star_balance:,} ⭐</b>\n"
        f"🎁 <b>Отправка подарков:</b> {gifts_status}\n"
        f"🎯 <b>Шанс выпадения:</b> <b>{config.gift_drop_chance:g}%</b>\n"
        f"👥 <b>Подключенная группа:</b> {target_chat_info}\n"
        f"🏷️ <b>Выбранные подарки:</b> {enabled_info}\n\n"
        "<b>📈 Статистика работы:</b>\n"
        f"💬 Обработано сообщений: <b>{stats['messages_processed']:,}</b>\n"
        f"🎉 Успешно отправлено подарков: <b>{stats['total_gifts_sent']:,}</b>\n"
        f"⭐ Всего потрачено Stars: <b>{stats['total_stars_spent']:,} ⭐</b>\n"
        f"👤 Уникальных победителей: <b>{stats['unique_winners']:,}</b>"
    )
    await message.reply(text, parse_mode="HTML")


@router.message(Command("reload"))
async def cmd_reload(message: Message, config: Config) -> None:
    """Handle /reload command — reload settings from .env."""
    try:
        new_cfg = load_config()
        config.gift_drop_chance = new_cfg.gift_drop_chance
        config.target_chat_id = new_cfg.target_chat_id
        config.enabled_gift_ids = new_cfg.enabled_gift_ids
        config.max_gift_price_stars = new_cfg.max_gift_price_stars
        config.stars_source = new_cfg.stars_source
        config.spam_cooldown_seconds = new_cfg.spam_cooldown_seconds
        config.admin_ids = new_cfg.admin_ids

        await message.reply(
            "🔄 <b>Настройки успешно перезагружены из <code>.env</code>!</b>\n\n"
            f"• Шанс: <b>{config.gift_drop_chance:g}%</b>\n"
            f"• Группа: <code>{config.target_chat_id or 'любая'}</code>\n"
            f"• Лимит цены: <b>{config.max_gift_price_stars or 'нет'} ⭐</b>",
            parse_mode="HTML",
        )
    except ConfigValidationError as e:
        await message.reply(f"❌ Ошибка валидации: {e}", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"❌ Ошибка перезагрузки: {e}", parse_mode="HTML")

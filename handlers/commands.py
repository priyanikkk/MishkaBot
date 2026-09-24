"""Public user commands: /start, /me, /top, /chance."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Config
from database import Database
from utils.gifts import gift_service
from utils.helpers import format_user_mention

router = Router(name="commands_router")


@router.message(Command("start"))
async def cmd_start(message: Message, config: Config) -> None:
    """Handle /start command."""
    target_info = f"в группе <code>{config.target_chat_id}</code>" if config.target_chat_id else "в этой группе"
    price_info = (
        f"до <b>{config.max_gift_price_stars} ⭐</b>"
        if config.max_gift_price_stars > 0
        else "любые доступные в Telegram"
    )

    text = (
        "👋 <b>Привет! Я бот для розыгрыша НАСТОЯЩИХ Telegram Gifts 🎁</b>\n\n"
        f"Я работаю {target_info}. Каждое сообщение участников имеет шанс "
        f"<b>{config.gift_drop_chance:g}%</b> выиграть реальный подарок Telegram, "
        "который будет отправлен прямо в ваш профиль и оплачен Telegram Stars ⭐!\n\n"
        f"🏷️ <b>Категория подарков:</b> {price_info}\n\n"
        "<b>📋 Команды для участников:</b>\n"
        "• <code>/me</code> — посмотреть полученные подарки\n"
        "• <code>/top</code> — топ участников по подаркам\n"
        "• <code>/chance</code> — текущий шанс выпадения\n\n"
        "<b>👑 Команды администраторов:</b>\n"
        "• <code>/status</code> — статус подключения, баланс Stars и каталог Gifts\n"
        "• <code>/gifts</code> — список доступных подарков Telegram и их ID\n"
        "• <code>/setchance &lt;%&gt;</code> — изменить процент шанса выпадения\n"
        "• <code>/reload</code> — перезагрузить настройки\n\n"
        "<i>Просто общайтесь в чате и ловите подарки! ⭐</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("me"))
async def cmd_me(message: Message, database: Database) -> None:
    """Handle /me command — show user's received real Telegram gifts."""
    if not message.from_user:
        return

    stats = await database.get_user_gifts_stats(message.from_user.id)
    total_gifts = stats.get("total_gifts_received", 0)
    total_stars = stats.get("total_stars_value", 0)
    last_gift_at = stats.get("last_gift_at")

    if total_gifts == 0:
        await message.reply(
            "🎁 У вас пока нет выигранных подарков Telegram в этом чате.\n"
            "Продолжайте общаться, и вам обязательно улыбнется удача! ⭐",
            parse_mode="HTML",
        )
        return

    text = (
        "🎁 <b>Ваша статистика подарков:</b>\n\n"
        f"⭐ <b>Всего получено подарков:</b> {total_gifts} шт.\n"
        f"💎 <b>Общая стоимость в Stars:</b> {total_stars} ⭐\n"
        f"🕒 <b>Последний подарок:</b> {last_gift_at} UTC"
    )
    await message.reply(text, parse_mode="HTML")


@router.message(Command("top"))
async def cmd_top(message: Message, database: Database) -> None:
    """Handle /top command — leaderboard of real gift recipients."""
    top_users = await database.get_top_receivers(limit=10)

    if not top_users:
        await message.reply(
            "🏆 <b>Топ получателей подарков:</b>\n\n"
            "Пока никто в чате не выиграл подарки. Будьте первыми! ⭐",
            parse_mode="HTML",
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Топ участников по полученным Telegram Gifts:</b>\n"]

    for idx, u in enumerate(top_users, start=1):
        medal = medals[idx - 1] if idx <= 3 else f"{idx}."
        mention = format_user_mention(
            user_id=u["user_id"],
            first_name=u["first_name"],
            username=u.get("username"),
        )
        total_g = u["total_gifts"]
        total_s = u["total_stars"]
        lines.append(f"{medal} {mention} — <b>{total_g}</b> подарков ({total_s} ⭐)")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("chance"))
async def cmd_chance(message: Message, config: Config) -> None:
    """Handle /chance command — show current gift drop chance."""
    price_info = (
        f"до {config.max_gift_price_stars} ⭐"
        if config.max_gift_price_stars > 0
        else "без ограничений цены"
    )
    filters_info = (
        f"выбрано {len(config.enabled_gift_ids)} конкретных подарков"
        if config.enabled_gift_ids
        else "все доступные подарки"
    )

    text = (
        "🎲 <b>Текущие настройки розыгрыша:</b>\n\n"
        f"🎯 <b>Шанс выпадения подарка:</b> <code>{config.gift_drop_chance:g}%</code> на каждое сообщение\n"
        f"💰 <b>Лимит стоимости:</b> {price_info}\n"
        f"🎁 <b>Пул подарков:</b> {filters_info}\n"
        f"⚡ <b>Задержка анти-спама:</b> {config.spam_cooldown_seconds:g} сек."
    )
    await message.reply(text, parse_mode="HTML")

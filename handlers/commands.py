"""Public commands handler: /start, /me, /top, /chance."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Config
from database import Database
from utils.helpers import escape_html, format_user_mention

router = Router(name="commands_router")


@router.message(Command("start"))
async def cmd_start(message: Message, config: Config) -> None:
    """Handle /start command."""
    text = (
        "👋 <b>Привет! Я MishkaBot 🐻</b>\n\n"
        "Я живу в вашем чате и дарю плюшевых мишек активным участникам! "
        f"Каждое обычное сообщение имеет шанс <b>{config.mishka_chance:g}%</b> принести награду.\n\n"
        "<b>📋 Доступные команды:</b>\n"
        "• <code>/me</code> — посмотреть свою коллекцию мишек\n"
        "• <code>/top</code> — топ участников по мишкам\n"
        "• <code>/chance</code> — узнать текущий шанс выпадения\n\n"
        "<b>👑 Команды администраторов:</b>\n"
        "• <code>/setchance &lt;процент&gt;</code> — изменить общий шанс\n"
        "• <code>/settype &lt;тип&gt; &lt;процент&gt;</code> — настроить шанс конкретного типа\n"
        "• <code>/stats</code> — статистика работы бота\n"
        "• <code>/reload</code> — перезагрузить настройки\n\n"
        "<i>Просто общайтесь в чате и собирайте свою коллекцию! 🧸</i>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("me"))
async def cmd_me(message: Message, database: Database) -> None:
    """Handle /me command — show user statistics."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    user_stats = await database.get_user_stats(user_id)

    if not user_stats or user_stats.get("total_count", 0) == 0:
        await message.reply(
            "🐻 У тебя пока нет мишек!\n"
            "Просто продолжай общаться в чате, и скоро тебе обязательно улыбнется удача! 🍀",
            parse_mode="HTML",
        )
        return

    common = user_stats.get("common_count", 0)
    rare = user_stats.get("rare_count", 0)
    epic = user_stats.get("epic_count", 0)
    legendary = user_stats.get("legendary_count", 0)
    total = user_stats.get("total_count", 0)

    text = (
        "🐻 <b>Твоя статистика:</b>\n\n"
        f"🧸 Обычных: <b>{common}</b>\n"
        f"🐻 Редких: <b>{rare}</b>\n"
        f"🐼 Эпических: <b>{epic}</b>\n"
        f"🐨 Легендарных: <b>{legendary}</b>\n\n"
        f"🎁 <b>Всего мишек: {total}</b>"
    )
    await message.reply(text, parse_mode="HTML")


@router.message(Command("top"))
async def cmd_top(message: Message, database: Database) -> None:
    """Handle /top command — leaderboard of bear collectors."""
    top_users = await database.get_top_users(limit=10)

    if not top_users:
        await message.reply(
            "🏆 <b>Топ коллекционеров мишек:</b>\n\n"
            "Пока никто не нашел ни одного мишки. Будьте первыми! 🐻",
            parse_mode="HTML",
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Топ коллекционеров мишек:</b>\n"]

    for idx, u in enumerate(top_users, start=1):
        medal = medals[idx - 1] if idx <= 3 else f"{idx}."
        user_id = u["user_id"]
        first_name = u["first_name"] or "Пользователь"
        username = u.get("username")
        mention = format_user_mention(user_id=user_id, first_name=first_name, username=username)
        total = u.get("total_count", 0)
        lines.append(f"{medal} {mention} — <b>{total}</b> шт.")

    await message.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("chance"))
async def cmd_chance(message: Message, config: Config) -> None:
    """Handle /chance command — show current drop chances."""
    text = (
        "🎲 <b>Текущие вероятности получения мишек:</b>\n\n"
        f"🎯 <b>Общий шанс:</b> <code>{config.mishka_chance:g}%</code> на каждое сообщение\n\n"
        "<b>Распределение по редкости (среди выпавших):</b>\n"
        f"🧸 <b>Обычный:</b> <code>{config.common_chance:g}%</code>\n"
        f"🐻 <b>Редкий:</b> <code>{config.rare_chance:g}%</code>\n"
        f"🐼 <b>Эпический:</b> <code>{config.epic_chance:g}%</code>\n"
        f"🐨 <b>Легендарный:</b> <code>{config.legendary_chance:g}%</code>\n\n"
        f"<i>Сумма типов: {config.common_chance + config.rare_chance + config.epic_chance + config.legendary_chance:g}%</i>"
    )
    await message.reply(text, parse_mode="HTML")

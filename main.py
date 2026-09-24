"""Main entry point for Telegram Gifts & Stars Bot."""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import ConfigValidationError, load_config
from database import Database
from handlers.admin import router as admin_router
from handlers.commands import router as commands_router
from handlers.messages import router as messages_router
from utils.gifts import gift_service
from utils.mtproto import MTProtoSessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gifts_bot")


async def main() -> None:
    """Bootstrap and start bot."""
    logger.info("Initializing Telegram Gifts & Stars Bot...")

    # 1. Load configuration
    try:
        config = load_config()
    except ConfigValidationError as e:
        logger.critical("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error loading configuration: %s", e)
        sys.exit(1)

    logger.info(
        "Config loaded: DROP_CHANCE=%s%%, TARGET_CHAT=%s, MAX_GIFT_PRICE=%s ⭐",
        config.gift_drop_chance,
        config.target_chat_id or "Any Group",
        config.max_gift_price_stars or "No Limit",
    )

    # 2. Initialize Database
    database = Database(config.database_path)
    try:
        await database.init_db()
        logger.info("Database initialized at %s", config.database_path)
    except Exception as e:
        logger.critical("Failed to initialize database: %s", e)
        sys.exit(1)

    # 3. Create Bot and Dispatcher
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["config"] = config
    dp["database"] = database

    dp.include_router(commands_router)
    dp.include_router(admin_router)
    dp.include_router(messages_router)

    # 4. Connect and verify with Telegram API
    try:
        bot_info = await bot.get_me()
        logger.info(
            "Bot connected: @%s (ID: %s, Name: %s)",
            bot_info.username,
            bot_info.id,
            bot_info.first_name,
        )
    except Exception as e:
        logger.critical("Failed to connect to Telegram with BOT_TOKEN: %s", e)
        await bot.session.close()
        sys.exit(1)

    # 5. Check real Telegram Stars balance and available gifts
    try:
        star_balance = await gift_service.get_star_balance(bot)
        logger.info("Current Telegram Stars balance: %d ⭐", star_balance)

        gifts = await gift_service.get_available_gifts(bot)
        logger.info("Available Telegram Gifts catalog: %d items", len(gifts))
        if star_balance == 0:
            logger.warning(
                "NOTE: Bot Stars balance is currently 0 ⭐. "
                "Top up Stars in Telegram or send Stars to the bot to enable real gift drops."
            )
    except Exception as e:
        logger.warning("Could not query initial Stars/Gifts status: %s", e)

    # 6. Check MTProto session if configured
    session_mgr = MTProtoSessionManager(config)
    if session_mgr.is_configured():
        is_auth, info = await session_mgr.check_session_status()
        logger.info("MTProto User Session: %s", info)

    # 7. Start polling
    try:
        logger.info("Starting updates polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("Bot is stopping...")
    finally:
        await bot.session.close()
        logger.info("Bot stopped. Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

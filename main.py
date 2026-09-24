"""Main entry point for MishkaBot."""

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

# Configure clean logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("mishkabot")


async def main() -> None:
    """Bootstrap and start MishkaBot."""
    logger.info("Initializing MishkaBot...")

    # 1. Load and validate configuration
    try:
        config = load_config()
    except ConfigValidationError as e:
        logger.critical("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.critical("Unexpected error loading configuration: %s", e)
        sys.exit(1)

    logger.info(
        "Config loaded successfully: MISHKA_CHANCE=%s%% (common=%s%%, rare=%s%%, epic=%s%%, legendary=%s%%)",
        config.mishka_chance,
        config.common_chance,
        config.rare_chance,
        config.epic_chance,
        config.legendary_chance,
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

    # Pass dependencies to all handlers via workflow data
    dp["config"] = config
    dp["database"] = database

    # Register routers in priority order
    dp.include_router(commands_router)
    dp.include_router(admin_router)
    dp.include_router(messages_router)

    # 4. Verify Bot Credentials with Telegram
    try:
        bot_info = await bot.get_me()
        logger.info(
            "Bot connected successfully as @%s (ID: %s, Name: %s)",
            bot_info.username,
            bot_info.id,
            bot_info.first_name,
        )
    except Exception as e:
        logger.critical("Failed to connect to Telegram with provided BOT_TOKEN: %s", e)
        await bot.session.close()
        sys.exit(1)

    # 5. Start Polling
    try:
        logger.info("Starting polling updates...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("Bot is shutting down...")
    finally:
        await bot.session.close()
        logger.info("Bot session closed. Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

"""Interactive setup wizard for Telegram Gifts & Stars Bot."""

import asyncio
import os
import sys
from pathlib import Path

from config import Config, load_config, update_env_variable


async def run_wizard() -> None:
    print("\n" + "=" * 60)
    print("⭐ НАСТРОЙКА TELEGRAM GIFTS & STARS BOT ⭐")
    print("=" * 60)
    print("Этот мастер настроит бота для работы с реальными Telegram Gifts и Stars.\n")

    # Ensure .env exists
    env_file = Path(".env")
    if not env_file.exists():
        if Path(".env.example").exists():
            env_file.write_text(Path(".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_file.write_text("BOT_TOKEN=\nGIFT_DROP_CHANCE=5\n", encoding="utf-8")

    cfg = load_config(env_file) if env_file.exists() and os.getenv("BOT_TOKEN") else None

    # 1. Telegram Bot Token
    current_token = os.getenv("BOT_TOKEN") or (cfg.bot_token if cfg else "")
    if current_token:
        print(f"ℹ️ Текущий Bot Token: {current_token[:10]}...{current_token[-5:]}")
        change = input("Хотите изменить Bot Token? (y/N): ").strip().lower()
        if change in ("y", "yes", "д", "да"):
            current_token = ""

    while not current_token:
        current_token = input("👉 Введите Telegram Bot Token (от @BotFather): ").strip()
        if not current_token:
            print("⚠️ Токен не может быть пустым.")

    update_env_variable("BOT_TOKEN", current_token)

    # Verify Bot Token with Telegram
    print("\n[Проверка Bot Token...]")
    bot = None
    try:
        from aiogram import Bot
        bot = Bot(token=current_token)
        me = await bot.get_me()
        print(f"✅ Успешное подключение к боту @{me.username} ({me.first_name})!")

        # Check Star balance
        try:
            star_amt = await bot.get_my_star_balance()
            balance = star_amt.amount
            print(f"⭐ Баланс Telegram Stars бота: {balance:,} ⭐")
            if balance == 0:
                print("ℹ️ Внимание: Баланс Stars бота равен 0. Вы сможете пополнить его позже через Telegram.")
        except Exception as e:
            print(f"ℹ️ Статус Stars бота: {e}")

        # Check Available Gifts
        try:
            gifts_obj = await bot.get_available_gifts()
            gifts = gifts_obj.gifts if gifts_obj else []
            print(f"🎁 Доступно официальных Telegram Gifts в каталоге: {len(gifts)} шт.")
        except Exception as e:
            print(f"ℹ️ Каталог подарков: {e}")

    except Exception as e:
        print(f"❌ Ошибка проверки токена бота: {e}")
        print("Вы сможете скорректировать токен в файле .env.")

    # 2. Какой источник Stars использовать
    print("\n---------------------------------------------------------")
    print("Источник Telegram Stars для оплаты подарков:")
    print("1) Баланс самого бота (Рекомендуется Telegram Bot API 8.0+)")
    print("2) Пользовательский Telegram-аккаунт (MTProto User Session)")
    stars_choice = input("Выберите вариант [1]: ").strip()
    if stars_choice == "2":
        update_env_variable("STARS_SOURCE", "user_session")
        print("\nДля подключения Telegram-аккаунта требуются API_ID и API_HASH с my.telegram.org:")
        api_id_in = input("Введите Telegram API ID: ").strip()
        api_hash_in = input("Введите Telegram API HASH: ").strip()
        phone_in = input("Введите номер телефона (+7...): ").strip()

        if api_id_in and api_hash_in and phone_in:
            update_env_variable("TELEGRAM_API_ID", api_id_in)
            update_env_variable("TELEGRAM_API_HASH", api_hash_in)
            update_env_variable("TELEGRAM_PHONE", phone_in)

            # Interactive MTProto login
            from utils.mtproto import interactive_login
            print("\nЗапуск авторизации пользовательской сессии...")
            try:
                await interactive_login(int(api_id_in), api_hash_in, phone_in)
            except Exception as e:
                print(f"⚠️ Не удалось завершить авторизацию: {e}")
    else:
        update_env_variable("STARS_SOURCE", "bot")
        print("✅ Выбран баланс самого бота (официальный Bot API).")

    # 3. ID группы
    print("\n---------------------------------------------------------")
    target_chat = input(
        "👉 Введите ID группы Telegram (например, -1001234567890)\n"
        "(Нажмите Enter, чтобы бот работал в любой группе, где он состоит): "
    ).strip()
    if target_chat:
        update_env_variable("TARGET_CHAT_ID", target_chat)
        print(f"✅ Привязана группа: {target_chat}")
    else:
        update_env_variable("TARGET_CHAT_ID", "")
        print("✅ Бот будет работать в любой группе, где он назначен администратором.")

    # 4. Процент выпадения
    print("\n---------------------------------------------------------")
    chance_in = input("👉 Введите процент шанса выпадения подарка на сообщение (по умолчанию: 5): ").strip()
    if chance_in:
        try:
            val = float(chance_in.replace(",", "."))
            if 0.0 <= val <= 100.0:
                update_env_variable("GIFT_DROP_CHANCE", f"{val:g}")
                print(f"✅ Шанс установлен на {val:g}%")
            else:
                print("⚠️ Некорректное значение, оставлен шанс 5%")
        except ValueError:
            print("⚠️ Некорректное значение, оставлен шанс 5%")
    else:
        update_env_variable("GIFT_DROP_CHANCE", "5")
        print("✅ Шанс установлен на 5%")

    # 5. Максимальная цена подарка
    print("\n---------------------------------------------------------")
    max_price = input("👉 Максимальная стоимость подарка в Stars (0 — без ограничений) [50]: ").strip()
    if max_price.isdigit():
        update_env_variable("MAX_GIFT_PRICE_STARS", max_price)
    else:
        update_env_variable("MAX_GIFT_PRICE_STARS", "50")

    if bot:
        await bot.session.close()

    print("\n" + "=" * 60)
    print("🎉 НАСТРОЙКА УСПЕШНО ЗАВЕРШЕНА!")
    print("Конфигурация сохранена в файл .env")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_wizard())

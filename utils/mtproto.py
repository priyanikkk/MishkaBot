"""Optional MTProto client session manager using Telethon."""

import logging
from pathlib import Path
from typing import Optional, Tuple
from config import Config

logger = logging.getLogger(__name__)


class MTProtoSessionManager:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = None

    def is_configured(self) -> bool:
        """Check if Telegram Client API credentials are provided."""
        return bool(self.config.telegram_api_id and self.config.telegram_api_hash)

    def session_exists(self) -> bool:
        """Check if a session file already exists on disk."""
        session_file = Path(f"{self.config.session_name}.session")
        return session_file.exists()

    async def get_client(self):
        """Lazy load and return Telethon TelegramClient instance."""
        if not self.is_configured():
            return None

        if self._client is not None:
            return self._client

        try:
            from telethon import TelegramClient

            # Ensure parent secrets directory exists
            session_path = Path(self.config.session_name)
            session_path.parent.mkdir(parents=True, exist_ok=True)

            self._client = TelegramClient(
                self.config.session_name,
                self.config.telegram_api_id,
                self.config.telegram_api_hash,
            )
            return self._client
        except Exception as e:
            logger.error("Failed to initialize Telethon TelegramClient: %s", e)
            return None

    async def check_session_status(self) -> Tuple[bool, Optional[str]]:
        """
        Check if user session is authorized.
        Returns (is_authorized, user_display_info).
        """
        if not self.is_configured():
            return False, "Не настроены API_ID / API_HASH"

        client = await self.get_client()
        if client is None:
            return False, "Клиент не инициализирован"

        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                user_info = f"@{me.username}" if me.username else f"{me.first_name} (ID: {me.id})"
                return True, user_info
            return False, "Сессия не авторизована"
        except Exception as e:
            return False, f"Ошибка подключения: {e}"
        finally:
            if client.is_connected():
                await client.disconnect()


async def interactive_login(
    api_id: int,
    api_hash: str,
    phone: str,
    session_name: str = "secrets/user_session",
) -> bool:
    """
    Run interactive login for Telethon asking for SMS/Telegram code and 2FA password.
    Never persists password in plain text.
    """
    try:
        import getpass
        from telethon import TelegramClient

        Path(session_name).parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(session_name, api_id, api_hash)
        await client.connect()

        if await client.is_user_authorized():
            print("✅ Сессия уже успешно авторизована!")
            await client.disconnect()
            return True

        await client.send_code_request(phone)
        code = input(f"📲 Введите код подтверждения из Telegram для номера {phone}: ").strip()

        try:
            await client.sign_in(phone, code)
        except Exception as e:
            # Check for 2FA password requirement
            if "Two-step verification" in str(e) or "SessionPasswordNeededError" in type(e).__name__:
                pwd = getpass.getpass("🔐 Введите облачный пароль двухфакторной аутентификации (2FA): ")
                await client.sign_in(password=pwd)
            else:
                raise e

        me = await client.get_me()
        print(f"🎉 Авторизация успешна! Подключен аккаунт: {me.first_name} (ID: {me.id})")
        await client.disconnect()
        return True
    except Exception as e:
        print(f"❌ Ошибка авторизации клиентской сессии: {e}")
        return False

"""Custom aiogram filters for chat types and admin verification."""

from typing import Union, Sequence
from aiogram.filters import BaseFilter
from aiogram.types import Message, ChatMemberOwner, ChatMemberAdministrator

from config import Config


class ChatTypeFilter(BaseFilter):
    """Filter messages by chat type (e.g. group, supergroup, private)."""

    def __init__(self, chat_types: Union[str, Sequence[str]]) -> None:
        if isinstance(chat_types, str):
            self.chat_types = {chat_types}
        else:
            self.chat_types = set(chat_types)

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types


class AdminFilter(BaseFilter):
    """
    Filter verifying that the message author is an administrator of the group
    or a configured bot superadmin.
    """

    async def __call__(self, message: Message, config: Config) -> bool:
        if not message.from_user:
            return False

        user_id = message.from_user.id

        # 1. Check if user is in superadmin list from config
        if user_id in config.admin_ids:
            return True

        # 2. In private chats, only configured superadmins are admins
        if message.chat.type == "private":
            return False

        # 3. In groups/supergroups, dynamically query Telegram API
        try:
            member = await message.bot.get_chat_member(
                chat_id=message.chat.id,
                user_id=user_id,
            )
            return isinstance(member, (ChatMemberOwner, ChatMemberAdministrator)) or member.status in {
                "creator",
                "administrator",
            }
        except Exception:
            return False

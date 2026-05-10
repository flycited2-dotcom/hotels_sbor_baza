import logging
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import ALLOWED_USERS

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Блокирует доступ к боту для пользователей не из ALLOWED_USERS.
    Если ALLOWED_USERS пуст — доступ открыт всем."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        if not ALLOWED_USERS:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None or user.id in ALLOWED_USERS:
            return await handler(event, data)

        logger.warning(f"Access denied: user_id={user.id} username=@{user.username}")
        if isinstance(event, Message):
            await event.answer("⛔ У вас нет доступа к этому боту.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Нет доступа.", show_alert=True)
        return

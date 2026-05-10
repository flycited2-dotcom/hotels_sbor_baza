import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from services.db import init_db
from handlers import new_lead, commands
from handlers import inline
from middlewares.access import AccessMiddleware
from scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="new",       description="Добавить новый контакт"),
        BotCommand(command="status",    description="Статистика контактов"),
        BotCommand(command="report",    description="Отчёт за сегодня (Excel)"),
        BotCommand(command="week",      description="Отчёт за 7 дней (Excel)"),
        BotCommand(command="master",    description="Полная база (Excel)"),
        BotCommand(command="find",      description="Поиск по имени / телефону / городу"),
        BotCommand(command="getlead",   description="Карточка контакта по ID"),
        BotCommand(command="edit",      description="Последние 5 ваших контактов"),
        BotCommand(command="sync",      description="Синхронизировать с Google Sheets"),
        BotCommand(command="cancel",    description="Отменить текущее действие"),
        BotCommand(command="help",      description="Справка по командам"),
    ])


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан в .env")

    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — применяется ко всем входящим сообщениям и callback'ам
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    dp.include_router(commands.router)
    dp.include_router(inline.router)
    dp.include_router(new_lead.router)

    await set_commands(bot)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

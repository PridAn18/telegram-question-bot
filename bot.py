import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database import Database
from handlers import admin, questions, start
from utils.constants import APP_NAME, VERSION
from utils.logger import setup_logger


async def main() -> None:
    logger = setup_logger()
    logger.info("Запуск %s v%s", APP_NAME, VERSION)

    if not config.BOT_TOKEN:
        logger.critical("Не задан BOT_TOKEN. Добавь его в .env или окружение.")
        return

    db = Database(config.DATABASE_PATH)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp["db"] = db
    dp["logger"] = logger
    dp["started_at"] = time.monotonic()

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(questions.router)

    try:
        me = await bot.me()
        logger.info("Long polling запущен для @%s", me.username)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
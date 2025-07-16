import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from core.logging_config import setup_logging
from core.utils import get_str_env
from core.postgres_pool import PostgresPool
from core.database import AsyncDatabaseManager

from handlers import setup_dialog as setup_handlers
from handlers import common as common_handlers

# --- 1. Настройка и конфигурация ---
setup_logging()
logger = logging.getLogger(__name__)
load_dotenv()

BOT_TOKEN = get_str_env('BOT_TOKEN', 'default')
if BOT_TOKEN == 'default':
    logger.critical("Токен бота (BOT_TOKEN) не найден в .env файле!")
    exit("Токен бота не найден!")

DB_USER = get_str_env("DB_USER", "postgres")
DB_PASSWORD = get_str_env("DB_PASSWORD", "password")
DB_HOST = get_str_env("DB_HOST", "localhost")
DB_PORT = get_str_env("DB_PORT", "5432")
DB_NAME = get_str_env("DB_NAME", "your_mama_bot_db")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# --- 2. Главная функция для запуска ---
async def main():
    logger.info("Запуск бота...")


    storage = MemoryStorage()
    db_pool = PostgresPool(dsn=DATABASE_URL)

    try:
        await db_pool.create_pool()
        logger.info("Пул соединений с БД успешно создан.")
    except Exception as e:
        logger.critical(
            f"Критическая ошибка: не удалось подключиться к базе данных! Бот не может запуститься. Ошибка: {e}")
        return

    db_manager = AsyncDatabaseManager(pool=db_pool)


    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)


    dp["db"] = db_manager


    dp.include_router(common_handlers.router)
    dp.include_router(setup_handlers.router)


    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

    logger.info("Остановка бота...")
    if db_pool.is_connected:
        await db_pool.disconnect()
        logger.info("Пул соединений с БД успешно закрыт.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен по команде.")
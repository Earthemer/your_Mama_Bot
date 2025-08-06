import asyncio
import logging

from joblib.testing import param

from core import config
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from core.logging_config import setup_logging
from core.postgres_pool import PostgresPool
from core.database import AsyncDatabaseManager
from handlers import setup_dialog as setup_handlers
from handlers import common as common_handlers
from handlers import interactions as interactions_handlers
from core.llm_service import LLMManager
from core.scheduler import setup_scheduler

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    logger.info("Запуск бота...")
    storage = MemoryStorage()
    db_pool = PostgresPool(dsn=config.DATABASE_URL, params=config.POOL_PARAMETERS)
    llm_manager = LLMManager(api_key=config.GEMINI_API_KEY)

    try:
        await db_pool.create_pool()
        logger.info("Пул соединений с БД успешно создан.")
    except Exception as e:
        logger.critical(
            f"Критическая ошибка: не удалось подключиться к базе данных! Бот не может запуститься. Ошибка: {e}")
        return

    db_manager = AsyncDatabaseManager(pool=db_pool)
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    scheduler = setup_scheduler(db_manager)
    scheduler.start()

    dp["db"] = db_manager
    dp["llm"] = llm_manager
    dp["scheduler"] = scheduler

    dp.include_router(common_handlers.router)
    dp.include_router(setup_handlers.router)
    dp.include_router(interactions_handlers.router)

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

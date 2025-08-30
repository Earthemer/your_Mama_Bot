import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from core.config.parameters import (
    DATABASE_URL, POOL_PARAMETERS, GEMINI_API_KEY, BOT_TOKEN, REDIS_HOST, REDIS_PORT
)

from core.database.postgres_client import AsyncPostgresManager
from core.llm_service import LLMManager
from core.logging_config import setup_logging
from core.database.postgres_pool import PostgresPool
from core.database.redis_client import RedisClient

from handlers.routers import common as common_handlers, setup_dialog as setup_handlers
from handlers import operator

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    logger.info("Запуск бота...")
    storage = MemoryStorage()
    db_pool = PostgresPool(dsn=DATABASE_URL, params=POOL_PARAMETERS)
    llm_manager = LLMManager(api_key=GEMINI_API_KEY)
    redis_client = RedisClient(host=REDIS_HOST, port=REDIS_PORT)

    await db_pool.create_pool()
    await redis_client.connect()

    db_manager = AsyncPostgresManager(pool=db_pool)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    dp["db"] = db_manager
    dp["llm"] = llm_manager
    dp["redis"] = redis_client

    dp.include_router(common_handlers.router)
    dp.include_router(setup_handlers.router)
    dp.include_router(operator.router)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        if db_pool.is_connected:
            await db_pool.disconnect()
        await redis_client.disconnect()
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен по команде.")
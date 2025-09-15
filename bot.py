import asyncio
import logging
import requests
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.client.default import DefaultBotProperties

from core.config.parameters import (
    DATABASE_URL, POOL_PARAMETERS, GEMINI_API_KEY, BOT_TOKEN, REDIS_HOST, REDIS_PORT
)
from core.config.logging_config import setup_logging

from core.database.postgres_pool import PostgresPool
from core.database.postgres_client import AsyncPostgresManager
from core.database.redis_client import RedisClient
from core.personalities import PersonalityManager
from core.llm.gemini_client import GeminiClient
from core.llm.llm_processor import LLMProcessor
from core.prompt_factory import PromptFactory
from core.brain_service import BrainService
from core.operator_messages import Operator
from core.scheduler import SchedulerManager
from handlers import common, setup_dialog, listener

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    logger.info("Инициализация бота...")
    storage = RedisStorage.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/1")
    db_pool = PostgresPool(dsn=DATABASE_URL, **POOL_PARAMETERS)
    redis_client = RedisClient(host=REDIS_HOST, port=REDIS_PORT)

    scheduler = AsyncIOScheduler()

    await db_pool.create_pool()
    await redis_client.connect()

    db_manager = AsyncPostgresManager(pool=db_pool)
    personality_manager = PersonalityManager()
    gemini_client = GeminiClient(api_key=GEMINI_API_KEY)
    llm_processor = LLMProcessor(client=gemini_client)
    prompt_factory = PromptFactory()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    brain_service = BrainService(
        redis_client=redis_client,
        db_manager=db_manager,
        prompt_factory=prompt_factory,
        llm_processor=llm_processor,
        bot=bot
    )
    operator = Operator(redis_client=redis_client, brain_service=brain_service)
    scheduler_manager = SchedulerManager(
        scheduler=scheduler,
        redis_client=redis_client,
        db_manager=db_manager,
        brain_service=brain_service
    )
    dp = Dispatcher(storage=storage)

    dp["db"] = db_manager
    dp["redis"] = redis_client
    dp["operator"] = operator
    dp["personality_manager"] = personality_manager

    dp.include_router(common.router)
    dp.include_router(setup_dialog.router)
    dp.include_router(listener.router)

    await scheduler_manager.start()

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        logger.info("Бот запущен и готов к работе.")
        await dp.start_polling(bot)
    finally:
        logger.info("Бот останавливается...")
        if scheduler.running:
            scheduler.shutdown(wait=False)
        if db_pool.is_connected:
            await db_pool.disconnect()
        await redis_client.disconnect()
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
        logger.debug(requests.get("https://ifconfig.me").text)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.critical(f"Произошла критическая ошибка на верхнем уровне: {e}", exc_info=True)
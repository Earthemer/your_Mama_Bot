import logging
from aiogram import Bot

from core.exceptions import DatabaseQueryError
from core.logging_config import log_error
from core.exceptions import SchedulerError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.llm_service import LLMManager, LLMError
from core import config
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from core.database import AsyncDatabaseManager

logger = logging.getLogger(__name__)


async def switch_to_waiting_mode(chat_id: int, storage: BaseStorage, bot: Bot, llm: LLMManager):
    """Переключает режим бота в 'ожидание' по таймеру."""

    storage_key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=bot.id)

    await storage.set_data(key=storage_key, data={'mode': 'waiting'})

    prompt_for_llm = f"Сформулируй короткое прощание, будто тебе нужно уйти на работу, или куда то еще. Ты вернешься позже."
    llm_response = await llm.get_response(prompt_for_llm)

    await bot.send_message(chat_id, llm_response)
    logger.info(f"Для чата {chat_id} установлен 'Режим Ожидания'.")


@log_error
async def morning_routine(
        bot: Bot, db: AsyncDatabaseManager, llm: LLMManager, storage: BaseStorage,
        config: dict
):
    """
    Тестовая задача на 17:50.
    """
    try:
        if not (config := await db.get_mama_config(chat_id)):
            raise SchedulerError("Ошибка в получении конфигурации.")

        prompt = (f"Ты — {config['bot_name']}, заботливая 'мама на удаленке'.\n"
                  f"Твои черты характера: {config.get('personality_prompt', 'ты просто добрая и заботливая')}.\n"
                  f"Твоя задача: Сгенерируй ОДНО короткое (1-2 предложения) и уникальное "
                  f"приветственное сообщение для твоего чата. Просто поздоровайся и пожелай хорошего дня. И расскажи короткий, смешной анекдот в стиле 'мамы'"
                  )

        response_text = await llm.get_response(prompt)
        await bot.send_message(chat_id=chat_id, text=response_text)
        logger.info(f"Успешно отправлено сгенерированное сообщение в чат {chat_id}.")


    except LLMError:
        logger.error(f"Не удалось получить ответ от LLM для чата {chat_id}.")
        await bot.send_message(chat_id=chat_id, text="Хотела что-то сказать, но забыла...")
    except Exception as e:
        raise SchedulerError(f"Не удалось отправить тестовое сообщение в чат {chat_id}. Ошибка: {e}")


def add_chat_jobs_for_test(
        scheduler: AsyncIOScheduler, bot: Bot, db: AsyncDatabaseManager, llm: LLMManager,
        chat_id: int, timezone: str
):
    """
    Добавляет ОДНУ тестовую "работу" для чата на указанное время.
    """
    job_id = f"creative_test_{chat_id}"

    scheduler.add_job(
        morning_interaction,
        trigger='cron',
        hour=17,
        minute=50,
        timezone=timezone,
        kwargs={'bot': bot, 'db': db, 'llm': llm, 'chat_id': chat_id},
        id=job_id,
        replace_existing=True
    )
    logger.info(f"Для чата {chat_id} добавлена творческая тестовая задача на 17:50 ({timezone}).")


def setup_scheduler(db: AsyncDatabaseManager) -> AsyncIOScheduler:
    """
    Создает и возвращает пустой экземпляр планировщика.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    logger.info("Планировщик инициализирован.")
    return scheduler

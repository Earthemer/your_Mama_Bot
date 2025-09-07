import logging

from aiogram import Bot

from core.database.postgres_client import AsyncPostgresManager
from core.database.redis_client import RedisClient
from core.exceptions import BrainServiceError
from core.llm_processor import LLMProcessor
from core.logging_config import log_error
from core.prompt_factory import PromptFactory

logger = logging.getLogger(__name__)


class BrainService:
    """
    Мозг бота, принимает решение на основе данных из Redis и PostgreSQL,
    использует PromtFactory для создания промптов и LLMProcessor для их выполнения.
    """
    def __init__(
            self,
            redis_client: RedisClient,
            db_manager: AsyncPostgresManager,
            prompt_factory: PromptFactory,
            llm_processor: LLMProcessor,
            bot: Bot
    ):
        self.redis = redis_client
        self.db = db_manager
        self.prompts = prompt_factory
        self.llm = llm_processor
        self.bot = bot
        logger.info("BrainService инициализирован.")

    @log_error
    async def process_gathering_queues(self, config_id: int):
        """
        Главный метод для пакетной обработки. Запускается из scheduler.
        1. Собирает весь контекст (конфиг, участники, сообщения).
        2. Генерирует промпт.
        3. Выполняет промт и получается структуированный ответ.
        4. Отправляет текстовый ответ в чат.
        5. Выполняет действие по обновления в БД.
        """
        logger.debug(f"Начинаю пакетную обработку для config_id={config_id}...")

        config = await self.db.get_mama_config_by_id(config_id)
        if not config:
            raise BrainServiceError(f"Не найден конфиг с id={config_id}. Обработка прервана.")

        participants = await self.db.get_all_participants_by_config_id(config_id)

        direct_queue = f"direct_queue:{config_id}"
        background_queue = f"background_queue:{config_id}"

        direct_messages = await self.redis.get_and_clear_batch(direct_queue)
        background_messages = await self.redis.get_and_clear_batch(background_queue)
        all_messages = direct_messages + background_messages

        if not all_messages:
            logger.info(f"Нет сообщений для обработки в config_id={config_id}. Пропускаю.")
            return





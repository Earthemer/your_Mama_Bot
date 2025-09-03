import logging
import random
from aiogram import types

from core.database.redis_client import RedisClient
from core.logging_config import log_error
from core.config.parameters import (
    PASSIVE_MODE_CHANCE,
    ONLINE_MODE_REPLY_LIMIT,
    ONLINE_MODE_USER_COOLDOWN_SECONDS,
    ONLINE_MODE_BATCH_THRESHOLD
)
from handlers.brain_service import BrainService

logger = logging.getLogger(__name__)


class Operator:
    """Главный диспетчер. Получает сообщения от роутера и, в зависимости от режимов Redis."""

    def __init__(self, redis_client: RedisClient, brain_service: BrainService):
        self.redis = redis_client
        self.brain = brain_service
        logger.info("Operator инициализирован.")

    @staticmethod
    @log_error
    def _is_direct_mention(message: types.Message, bot_name: str) -> bool:
        """Проверяет, является ли сообщение прямым упоминаниемю."""
        if not message.text:
            return False
        if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            return True
        if bot_name.lower() in message.text.lower():
            return True
        return False

    @staticmethod
    @log_error
    def _is_child(config: dict, participant: dict | None) -> bool:
        """Проверяет, является ли автор сообщение 'ребенком'."""
        if not participant:
            return False
        return participant['id'] == config.get('child_participant_id')

    @staticmethod
    @log_error
    def _create_payload(message: types.Message, participant: dict | None) -> dict:
        """Создает стандартизированный dict для отправки в очередь."""
        return {
            "user_id": message.from_user.id,
            "chat_id": message.chat.id,
            "text": message.text,
            "timestamp": message.date.timestamp(),
            "participant_info": participant
        }

    @log_error
    async def handle_message(
            self,
            message: types.Message,
            config: dict,
            participant: dict | None
    ):
        """Главная точка входа в логику Оператора."""
        mode = await self.redis.get_mode(config['id'])

        if not mode:
            logger.warning(f"Для чата {config['id']} не установлен режим. Сообщение проигнорировано.")
            return

        if mode == 'GATHERING':
            await self._handle_gathering_mode(message, config, participant)
        elif mode == 'PASSIVE':
            await self._handle_passive_mode(message, config, participant)
        elif mode == 'ONLINE':
            await self._handle_online_mode(message, config, participant)

    @log_error
    async def _handle_gathering_mode(self, message: types.Message, config: dict, participant: dict | None):
        """Сценарий А: Просто сортируем сообщения по очередям."""
        payload = self._create_payload(message, participant)

        if self._is_direct_mention(message, config['bot_name']) or self._is_child(config, participant):
            queue_name = f"direct_queue:{config['id']}"
            await self.redis.enqueue(queue_name, payload)
            logger.debug(f"Сообщение добавлено в {queue_name}")
        else:
            queue_name = f"background_queue:{config['id']}"
            await self.redis.enqueue(queue_name, payload)
            logger.debug(f"Сообщение добавлено в {queue_name}")

    @log_error
    async def _handle_passive_mode(self, message: types.Message, config: dict, participant: dict | None):
        """Сценарий Б: Реагируем только на важное, и то не всегда."""

        if self._is_child(config, participant):
            payload = self._create_payload(message, participant)
            queue_name = f"direct_queue:{config['id']}"
            await self.redis.enqueue(queue_name, payload)
            logger.debug(f"Сообщение от 'ребенка' сохранено в {queue_name} для отложенной обработки.")
            return

        if self._is_direct_mention(message, config['bot_name']):
            if random.randint(1, 100) <= PASSIVE_MODE_CHANCE:
                logger.debug(f"Кубик в PASSIVE режиме сработал. Запускаем немедленную обработку.")
                await self.brain.process_single_message_immediately(message, config, participant)
            else:
                logger.debug("Кубик в PASSIVE режиме НЕ сработал. Сообщение проигнорировано.")

    @log_error
    async def _handle_online_mode(self, message: types.Message, config: dict, participant: dict | None):
        """Сценарий В: 'Микро-пакеты' для живого общения."""
        user_id = message.from_user.id

        replies_key = f"online_replies_count:{config['id']}"
        current_replies = await self.redis.increment_counter(replies_key) - 1  # Увеличили и откатили для проверки

        if current_replies >= ONLINE_MODE_REPLY_LIMIT:
            logger.warning(f"Достигнут лимит ответов ({ONLINE_MODE_REPLY_LIMIT}) в ONLINE режиме.")
            await self.brain.say_goodbye_and_switch_to_passive(config['id'])

        cooldown_key = f"online_user_cooldown:{config['id']}:{user_id}"
        if await self.redis.get_flag(cooldown_key):
            logger.info(f"Сработал кулдаун для пользователя {user_id}. Сообщение проигнорировано.")
            return

        payload = self._create_payload(message, participant)
        batch_queue = f"online_batch_queue:{config['id']}"
        await self.redis.enqueue(batch_queue, payload)

        await self.redis.set_flag(cooldown_key, True, ttl_seconds=ONLINE_MODE_USER_COOLDOWN_SECONDS)

        batch_size = await self.redis.get_queue_size(batch_queue)
        if batch_size >= ONLINE_MODE_BATCH_THRESHOLD:
            logger.info(f"Микро-пакет достиг размера {batch_size}. Запускаем обработку.")
            await self.brain.process_online_batch(config['id'])










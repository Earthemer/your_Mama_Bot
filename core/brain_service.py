import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from core.database.postgres_client import AsyncPostgresManager
from core.database.redis_client import RedisClient
from core.exceptions import BrainServiceError
from core.llm_processor import LLMProcessor
from core.logging_config import log_error
from core.prompt_factory import PromptFactory
from core.scheduler import BotMode
from core.config.parameters import SHORT_TERM_MEMORY_LIMIT, SHORT_TERM_MEMORY_TTL

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
    async def process_gathering_queues(self, config_id: int, time_of_day):
        """
        Главный метод для пакетной обработки. Запускается из scheduler.
        1. Собирает весь контекст (конфиг, участники, сообщения).
        2. Генерирует промпт.
        3. Выполняет промпт и получает структурированный ответ.
        4. Отправляет текстовый ответ в чат.
        5. Выполняет действие по обновления в БД.
        """
        logger.debug(f"Начинаю пакетную обработку для config_id={config_id} (контекст: {time_of_day})...")

        config = await self.db.get_mama_config_by_id(config_id)
        if not config:
            raise BrainServiceError(f"Не найден конфиг с id={config_id}. Обработка прервана.")

        participants = await self.db.get_all_participants_by_config_id(config_id)
        participants_map = {p['user_id']: p for p in participants}

        direct_messages = await self.redis.get_and_clear_batch(f"direct_queue:{config_id}")
        background_messages = await self.redis.get_and_clear_batch(f"background_queue:{config_id}")
        all_messages = sorted(direct_messages + background_messages, key=lambda msg: msg.get('timestamp', 0))

        if not all_messages:
            logger.info(f"Нет сообщений для обработки в config_id={config_id}. Пропускаю.")
            return

        child = next((p for p in participants if p['id'] == config.get('child_participant_id')), None)
        if not child:
            logger.warning(f"Для config_id={config_id} не назначен 'ребенок'. Логика child_was_active пропускается.")
        child_was_active = any(
            msg.get('participant_info', {}).get('id') == child['id']
            for msg in all_messages
        ) if child else False

        prompt = self.prompts.create_gathering_prompt(
            config=config,
            participants=participants,
            messages=all_messages,
            time_of_day=time_of_day,
            child_was_active=child_was_active
        )

        llm_response = await self.llm.execute_and_parse(prompt)
        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response.data_json:
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config['id'],
                participants_map=participants_map
            )

    @log_error
    async def process_online_batch(self, config_id: int):
        """Обрабатывает микро-пакет из Redis в Online режиме."""
        logger.info(f"Обрабатываю микро-пакет для config_id={config_id}...")

        if not (online_messages := await self.redis.get_and_clear_batch(f"online_batch_queue:{config_id}")):
            return

        if not (config := await self.db.get_mama_config_by_id(config_id)):
            raise BrainServiceError(f"Не найден конфиг с id={config_id} для онлайн-пакета.")

        memory_key = f"short_term_memory:{config_id}"
        dialog_history = await self.redis.get_json(memory_key) or []
        full_dialog = dialog_history + online_messages

        prompt = self.prompts.create_online_prompt(config, full_dialog)
        llm_response = await self.llm.execute_and_parse(prompt)

        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response.text_reply:
            full_dialog.append({'role': 'model', 'content': llm_response.text_reply})

        updated_memory = full_dialog[-SHORT_TERM_MEMORY_LIMIT:]
        await self.redis.set_json(memory_key, updated_memory, ttl_seconds=SHORT_TERM_MEMORY_TTL)

        if llm_response.data_json:
            participants = await self.db.get_all_participants_by_config_id(config_id)
            participants_map = {p['user_id']: p for p in participants}
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config_id,
                participants_map=participants_map
            )

    @log_error
    async def process_single_message_immediately(self, message: dict, config: dict):
        """Обрабатывает одиночное сообщение в реальном времени (для PASSIVE режима)."""
        config_id = config['id']
        logger.debug(f"Обрабатываю одиночное сообщение для config_id={config_id}...")

        all_participants = await self.db.get_all_participants_by_config_id(config_id)
        participants_map = {p['user_id']: p for p in all_participants}

        prompt = self.prompts.create_single_reply_prompt(
            config=config,
            participants=all_participants,
            message=message
        )
        llm_response = await self.llm.execute_and_parse(prompt)
        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response.data_json:
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config_id,
                participants_map=participants_map
            )

    @log_error
    async def say_goodbye_and_switch_to_passive(self, config_id: int):
        """
        Завершает ONLINE сессию: обрабатывает последний "хвост" сообщений,
        прощается в ОДНОМ сообщении и меняет режим на PASSIVE.
        """
        logger.info(f"Завершаю ONLINE сессию для config_id={config_id}...")

        config = await self.db.get_mama_config_by_id(config_id)
        if not config:
            await self.redis.set_mode(config_id, BotMode.PASSIVE.value)
            logger.warning(f"Не найден конфиг с id={config_id} для прощания. Просто меняю режим.")
            return

        last_messages = await self.redis.get_and_clear_batch(f"online_batch_queue:{config_id}")
        memory_key = f"short_term_memory:{config_id}"
        dialog_history = await self.redis.get_json(memory_key) or []
        full_dialog_for_prompt = dialog_history + last_messages

        prompt = self.prompts.create_final_reply_prompt(config, full_dialog_for_prompt)
        llm_response = await self.llm.execute_and_parse(prompt)

        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response.data_json and last_messages:
            participants = await self.db.get_all_participants_by_config_id(config_id)
            participants_map = {p['user_id']: p for p in participants}
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config_id,
                participants_map=participants_map
            )

        await self.redis.set_mode(config_id, BotMode.PASSIVE.value)
        await self.redis.delete(memory_key)

        logger.info(f"Режим для config_id={config_id} переключен на PASSIVE. Сессия завершена.")

    @log_error
    async def _send_reply(self, chat_id: int, text: str):
        """Безопасная отправка сообщения в чат."""
        if not text:
            logger.warning(f"Попытка отправить пустое сообщение в чат {chat_id}. Отменено.")
            return
        try:
            await self.bot.send_message(chat_id, text)
            logger.debug(f"Отправлено сообщение в чат {chat_id}.")
        except TelegramAPIError as e:
            raise BrainServiceError(f"Ошибка API Telegram при отправке сообщения в чат {chat_id}: {e}") from e
        except Exception as e:
            raise BrainServiceError(f"Неизвестная ошибка при отправке сообщения в чат {chat_id}: {e}") from e

    @log_error
    async def _execute_db_actions(
            self,
            updates: list,
            new_participants: list,
            config_id: int,
            participants_map: dict[int, dict]
    ):
        """Приватный метод ("ActionExecutor"). Применяет изменения к БД."""
        logger.debug(f"Применяю обновления из JSON для config_id={config_id}...")

        for user_update in updates:
            user_id = user_update.get('user_id')
            if not user_id: continue

            participant = participants_map.get(user_id)
            if not participant:
                logger.warning(f"Получен update для неизвестного user_id={user_id}. Пропускаю.")
                continue

            if change := user_update.get('relationship_change'):
                await self.db.update_relationship_score(participant['id'], int(change))

            if memory := user_update.get('new_memory'):
                await self.db.add_long_term_memory(participant['id'], memory, 1)

        for new_user in new_participants:
            user_id = new_user.get('user_id')
            if not user_id or user_id in participants_map:
                logger.warning(f"Попытка добавить существующего/невалидного юзера user_id={user_id}. Пропускаю.")
                continue

            await self.db.add_participant(
                config_id=config_id,
                user_id=user_id,
                custom_name=new_user.get('suggested_name', 'Новичок'),
                gender=new_user.get('suggested_gender', 'unknown')
            )
        logger.debug(
            f"Применяю {len(updates)} апдейтов и {len(new_participants)} новых участников для config_id={config_id}...")

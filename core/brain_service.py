import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.database.postgres_client import AsyncPostgresManager
from core.database.redis_client import RedisClient
from core.config.exceptions import BrainServiceError
from core.llm.llm_processor import LLMProcessor
from core.config.logging_config import log_error
from core.prompt_factory import PromptFactory
from core.config.botmode import BotMode

logger = logging.getLogger(__name__)


class BrainService:
    """
    Мозг бота. Управляет жизненным циклом сессий с LLM,
    обрабатывает накопленные сообщения и живые диалоги.
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

    @staticmethod
    def _get_current_time(config: dict) -> datetime:
        """Получает текущее время в правильной таймзоне из конфига."""
        try:
            timezone = ZoneInfo(config.get("timezone", "UTC"))
            return datetime.now(timezone)
        except ZoneInfoNotFoundError:
            logger.warning(f"Некорректная таймзона в конфиге: '{config.get('timezone')}'. Использую UTC.")
            return datetime.now(ZoneInfo("UTC"))

    @log_error
    async def start_online_interactions(self, config_id: int, time_of_day):
        """
        Главный метод для пакетной обработки. Запускается из scheduler.
        1. Собирает весь контекст (конфиг, участники, сообщения).
        2. Генерирует промпт.
        3. Выполняет промпт и получает структурированный ответ.
        4. Отправляет текстовый ответ в чат.
        5. Выполняет действие по обновления в БД.
        """
        logger.debug(f"Запуск сессии для config_id={config_id} (контекст: {time_of_day})...")

        if not (config := await self.db.get_mama_config_by_id(config_id)):
            raise BrainServiceError(f"Не найден конфиг с id={config_id}.")

        participants = await self.db.get_all_participants_by_config_id(config_id)
        participants_map = {p['user_id']: p for p in participants}

        direct_messages = await self.redis.get_and_clear_batch(f"direct_queue:{config_id}")
        background_messages = await self.redis.get_and_clear_batch(f"background_queue:{config_id}")
        all_messages = sorted(direct_messages + background_messages, key=lambda msg: msg.get('timestamp', 0))

        if not all_messages:
            logger.info(f"Нет сообщений для обработки в config_id={config_id}. Пропускаю.")
            return

        child = next((p for p in participants if p['id'] == config.get('child_participant_id')), None)
        child_was_active = any(
            msg.get('user_id') == child['user_id'] for msg in all_messages
        ) if child else False

        current_time = self._get_current_time(config)

        system_prompt = self.prompts.create_session_start_prompt(
            config=config,
            participants=participants,
            messages=all_messages,
            time_of_day=time_of_day,
            child_was_active=child_was_active,
            current_time=current_time
        )

        llm_response = await self.llm.process_session_start(session_id=config_id,
                                                            system_prompt=system_prompt)

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
        """
        STATEFUL. Обрабатывает микро-пакет из Redis ВНУТРИ активной ONLINE сессии.
        """
        logger.info(f"Проверяю микро-пакет для config_id={config_id}...")

        if not (online_messages := await self.redis.get_and_clear_batch(f"online_batch_queue:{config_id}")):
            return

        if not (config := await self.db.get_mama_config_by_id(config_id)):
            raise BrainServiceError(f"Не найден конфиг с id={config_id} для отправки ответа.")

        logger.debug(f"Обнаружен пакет из {len(online_messages)} сообщений. Обрабатываю...")

        current_time = self._get_current_time(config)
        prompt = self.prompts.create_online_prompt(
            dialog_history=online_messages,
            current_time=current_time
        )

        llm_response = await self.llm.process_session_message(
            session_id=config_id,
            prompt=prompt
        )

        if not llm_response:
            logger.warning(f"LLM не вернул ответ для онлайн-пакета config_id={config_id}")
            return

        await self._send_reply(config['chat_id'], llm_response.text_reply)

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
    async def process_single_message_immediately(self, message_payload: dict, config: dict):
        """STATELESS. Обрабатывает одно сообщение в PASSIVE режиме."""
        config_id = config['id']
        logger.debug(f"Обрабатываю одиночное сообщение для config_id={config_id}...")

        all_participants = await self.db.get_all_participants_by_config_id(config_id)
        current_time = self._get_current_time(config)

        prompt = self.prompts.create_single_reply_prompt(
            config=config,
            participants=all_participants,
            message=message_payload,
            current_time=current_time
        )

        llm_response = await self.llm.process_single(prompt)

        if not llm_response:
            logger.error(f"LLM не вернул ответ для stateless-запроса config_id={config_id}")
            return

        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response.data_json:
            participants_map = {p['user_id']: p for p in all_participants}
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config_id,
                participants_map=participants_map
            )

    @log_error
    async def say_goodbye_and_switch_to_passive(self, config_id: int):
        """Идемпотентно завершает ONLINE сессию."""
        current_mode = await self.redis.get_mode(config_id)
        if current_mode != BotMode.ONLINE.value:
            logger.debug(
                f"Попытка завершить сессию для config_id={config_id}, но она уже не активна (режим: {current_mode}). Пропускаем.")
            return

        logger.info(f"Завершаю ONLINE сессию для config_id={config_id}...")

        config = await self.db.get_mama_config_by_id(config_id)
        if not config:
            await self.llm.process_session_end(session_id=config_id)
            await self.redis.set_mode(config_id, BotMode.PASSIVE.value)
            await self.redis.delete(f"online_replies_count:{config_id}")
            logger.warning(f"Не найден конфиг с id={config_id} для прощания. Просто меняю режим.")
            return

        last_messages = await self.redis.get_and_clear_batch(f"online_batch_queue:{config_id}")
        current_time = self._get_current_time(config)

        goodbye_prompt = self.prompts.create_final_reply_prompt(
            config=config,
            dialog_history=last_messages,
            current_time=current_time
        )

        llm_response = await self.llm.process_session_message(config_id, goodbye_prompt)

        await self._send_reply(config['chat_id'], llm_response.text_reply)

        if llm_response and llm_response.data_json and last_messages:
            participants = await self.db.get_all_participants_by_config_id(config_id)
            participants_map = {p['user_id']: p for p in participants}
            await self._execute_db_actions(
                updates=llm_response.data_json.get('updates', []),
                new_participants=llm_response.data_json.get('new_participants', []),
                config_id=config_id,
                participants_map=participants_map
            )

        await self.llm.process_session_end(session_id=config_id)
        await self.redis.set_mode(config_id, BotMode.PASSIVE.value)
        await self.redis.delete(f"online_replies_count:{config_id}")

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
            participants_map: dict
    ):
        """Приватный метод для применения изменений к БД."""
        logger.debug(f"Применяю обновления из JSON для config_id={config_id}...")

        for user_update in updates:
            user_id = user_update.get('user_id')
            if not user_id:
                continue

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
            f"Применены {len(updates)} апдейтов и {len(new_participants)} новых участников для config_id={config_id}.")

import logging
import asyncio
import asyncpg

from typing import Any
from asyncpg import exceptions as error_database
from datetime import datetime

from core.logging_config import log_error
from core.config.types import QueryMode
from core.database.postgres_pool import PostgresPool
from core.exceptions import (
    DatabaseConnectionError,
    DatabaseQueryError,
    UnexpectedError,
    PoolConnectionError
)
import core.sql_queries as queries

logger = logging.getLogger(__name__)


class AsyncPostgresManager:
    """
    Управляет асинхронными запросами к базе данных для проекта "Твоя Мама",
    используя предоставленный пул соединений.
    """

    def __init__(self, pool: PostgresPool):
        self._pool = pool
        logger.info(f"AsyncDatabaseManager инициализирован.")

    @staticmethod
    def _record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
        return dict(record) if record else None

    @staticmethod
    def _records_to_list_records(records: list[asyncpg.Record]) -> list[dict[str, Any]]:
        return [dict(record) for record in records]

    @log_error
    async def _execute(
            self,
            query: str,
            params: tuple = (),
            mode: QueryMode = 'execute',
            timeout: float | None = None
    ) -> Any | None:
        """
        Не работает без пула подключения!
        Args:
            :param query: SQL строки (плейсхолдеры $1, $2)
            :param params: Кортеж параметров для SQL.
            :param mode: Параметр для execution SQL:
                'execute': Возвращает количество затронутых строк (для INSERT/UPDATE/DELETE).
                'fetch_all': Возвращает все строки в виде списка словарей.
                'fetch_row': Возвращает одну строку в виде словаря или None, если данных нет.
                'fetch_val': Возвращает одно значение из первой строки или None, если данных нет.
            :param timeout: Опциональная команда задержки в секундах.
            :return: Зависит от mode:
                'execute': int(количество затронутых строк)
                'fetch_all': list[dict[str, Any]}
                'fetch_row': dict[str, Any] | None
                'fetch_val': Any | None
        """
        if not self._pool.is_connected:
            raise DatabaseConnectionError("Пул соединений (PostgresPool) не активен.")

        logger.debug(f"Executing SQL ({mode}), timeout: {timeout}.")
        try:
            async with self._pool.acquire(timeout=timeout) as conn:
                async with conn.transaction():
                    if mode == 'execute':
                        status = await conn.execute(query, *params, timeout=timeout)
                        return int(status.rsplit(" ", 1)[-1]) if status else 0
                    elif mode == 'fetch_all':
                        records = await conn.fetch(query, *params, timeout=timeout)
                        return self._records_to_list_records(records)
                    elif mode == 'fetch_row':
                        record = await conn.fetchrow(query, *params, timeout=timeout)
                        return self._record_to_dict(record)
                    elif mode == 'fetch_val':
                        return await conn.fetchval(query, *params, timeout=timeout)
                    else:
                        raise ValueError(f"Неправильный запрос к SQL: {mode}.")
        except PoolConnectionError as e:
            raise DatabaseConnectionError(f"Ошибка пула при выполнении SQL: {e}") from e
        except error_database.PostgresError as e:
            raise DatabaseQueryError(f"Ошибка запроса к базе данных: {e.__class__.__name__} - {e}") from e
        except asyncio.TimeoutError as e:
            raise DatabaseQueryError("Операция с базой данных завершилась по таймауту.") from e
        except Exception as e:
            raise UnexpectedError(f"Не предвидимая ошибка: {type(e).__name__}: {e}") from e

    async def upsert_mama_config(
            self,
            chat_id: int,
            bot_name: str,
            admin_id: int,
            timezone: str,
            personality_prompt: str = None
    ) -> int:
        """Создает или обновляет конфигурацию для бота в конкретном чате."""
        config_id = await self._execute(
            queries.UPSERT_MAMA_CONFIG,
            params=(chat_id, bot_name, admin_id, timezone, personality_prompt),
            mode='fetch_val'
        )
        logger.info(f"Конфигурация для чата {chat_id} успешно сохранена/обновлена.")
        return config_id

    async def get_mama_config(self, chat_id: int) -> dict | None:
        """Получает активную конфигурацию для бота по chat_id."""
        logger.debug(f"Запрос конфигурации для чата {chat_id}...")
        config_dict = await self._execute(
            queries.GET_MAMA_CONFIG,
            params=(chat_id,),
            mode='fetch_row'
        )
        if config_dict:
            logger.debug(f"Конфигурация для чата {chat_id} найдена.")
            return config_dict
        else:
            logger.debug(f"Активная конфигурация для чата {chat_id} не найдена.")
            return None

    async def get_mama_config_by_id(self, config_id: int):
        """Получается все информацию о боте по id из db."""
        logger.debug(f"Запрос конфигурации для чата {config_id}...")
        config_dict = await self._execute(
            queries.GET_MAMA_CONFIG_BY_ID,
            params=(config_id,),
            mode='fetch_row'
        )
        if config_dict:
            logger.debug(f"Конфигурация для чата {config_id} найдена.")
            return config_dict
        else:
            logger.debug(f"Активная конфигурация для чата {config_id} не найдена.")
            return None

    async def get_all_mama_configs(self) -> list[dict]:
        """Получает ID всех чатов, где настроена мама."""
        return await self._execute(queries.GET_ALL_MAMA_CONFIGS, mode='fetch_all')

    async def delete_mama_config(self, chat_id: int) -> int:
        """Удаляет конфигурацию для чата и возвращает количество удаленных строк."""
        logger.info(f"Запрос на удаление конфигурации для чата {chat_id}.")
        deleted_count = await self._execute(
            queries.DELETE_MAMA_CONFIG,
            params=(chat_id,),
            mode='execute'
        )
        if deleted_count > 0:
            logger.info(f"Конфигурация для чата {chat_id} успешно удалена.")
        else:
            logger.warning(f"Попытка удаления конфигурации для несуществующего чата {chat_id}.")
        return deleted_count

    async def add_participant(
            self,
            config_id: int,
            user_id: int,
            custom_name: str,
            gender: str,
    ) -> dict[str, Any]:
        """Добавляет пользователя в память бота, и возвращает dict с его уникальным ID и custom_name."""
        participant = await self._execute(
            queries.INSERT_PARTICIPANT,
            params=(config_id, user_id, custom_name, gender),
            mode='fetch_row'
        )
        logger.info(
            f"Для мамы с ID {config_id} добавлен участник {user_id}. Его ID в таблице: {participant}."
        )
        return participant

    async def set_child(self, child_participant_id, config_id):
        """Устанавливает ребенка для конкретной конфигураций мамы"""
        return await self._execute(queries.SET_CHILD, params=(child_participant_id, config_id), mode='execute')

    async def update_personality_prompt(self, prompt: str, config_id: int):
        await self._execute(queries.UPDATE_PERSONALITY_PROMPT, params=(prompt, config_id), mode='execute')

    async def get_participant(self, config_id: int, user_id: int) -> dict | None:
        """Получает полную информацию об участнике по его Telegram ID."""
        return await self._execute(queries.GET_PARTICIPANT, params=(config_id, user_id), mode='fetch_row')

    async def get_all_participants_by_config_id(self, config_id: int) -> list[dict]:
        """Получает СПИСОК ВСЕХ активных участников для указанной конфигурации."""
        return await self._execute(
            queries.GET_ALL_PARTICIPANTS_BY_CONFIG_ID,
            params=(config_id,),
            mode='fetch_all'
        )

    async def get_child(self, config_id: int) -> dict | None:
        """Получается ID и имя ребенка для текущей мамы."""
        return await self._execute(queries.GET_CHILD, params=(config_id,), mode='fetch_row')

    async def update_relationship_score(self, participant_id: int, score_change: int) -> None:
        """Обновляет только репутацию участника."""
        await self._execute(queries.UPDATE_RELATIONSHIP_SCORE, params=(score_change, participant_id), mode='execute')

    async def set_ignore_status(self, participant_id: int, status: bool) -> None:
        """Устанавливает флаг is_ignored для участника и опускает relationship_score до 0"""
        await self._execute(queries.SET_IGNORED_STATUS, params=(status, participant_id), mode='execute')

    async def add_message_log(
            self,
            config_id: int,
            user_id: int,
            message_type: str,
            participant_id: int | None = None,
            message_text: str | None = None
    ) -> datetime:
        """Логируем сообщение и ВОЗВРАЩАЕМ его точное время создания из БД."""
        created_at = await self._execute(
            queries.INSERT_MESSAGE_LOG,
            params=(config_id, participant_id, user_id, message_text, message_type),
            mode='fetch_val'
        )
        return created_at

    async def get_message_log_for_processing(self, config_id: int, created_at: datetime) -> list[
        dict]:
        """Возвращает пакет сообщений в указанный промежуток времени."""
        return await self._execute(queries.GET_MESSAGE_LOG_FOR_PROCESSING, params=(config_id, created_at),
                                   mode='fetch_all')

    async def delete_processed_messages(self, config_id: int, created_at: datetime) -> None:
        """Удаляет пакет сообщение в указанный промежуток времени."""
        return await self._execute(queries.DELETE_PROCESSED_MESSAGES, params=(config_id, created_at), mode='execute')

    async def add_long_term_memory(self, participant_id, memory_summary, importance_level) -> None:
        """Запоминаем важное событие или действие."""
        return await self._execute(
            queries.INSERT_LONG_TERM_MEMORY,
            params=(participant_id, memory_summary, importance_level),
            mode='execute'
        )

    async def get_long_term_memory(self, participant_id: int, limit_logs: int) -> dict | None:
        """Возвращаем данные сохраненные в памяти о пользователе."""
        return await self._execute(queries.GET_LONG_TERM_MEMORY, params=(participant_id, limit_logs), mode='fetch_row')

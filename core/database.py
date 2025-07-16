import logging
from core.logging_config import log_error
import asyncio
import asyncpg
from typing import Any, Literal
from asyncpg import exceptions as error_database
from core.postgres_pool import PostgresPool
from core.exceptions import (
    DatabaseConnectionError,
    DatabaseQueryError,
    UnexpectedError,
    PoolConnectionError
)
import core.sql_queries as queries

logger = logging.getLogger(__name__)

QueryResult = list[dict[str, Any]]
QueryMode = Literal['execute', 'fetch_all', 'fetch_row', 'fetch_val']


class AsyncDatabaseManager:
    """
    Управляет асинхронными запросами к базе данных для проекта "Твоя Мама",
    используя предоставленный пул соединений.
    """

    def __init__(self, pool: PostgresPool):
        self._pool = pool
        logger.info(f"AsyncDatabaseManager инициализирован.")

    @staticmethod
    @log_error
    def _record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
        return dict(record) if record else None

    @staticmethod
    @log_error
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
            :param query: SQL строки (используем плейсхолдеры $1, $2)
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

    @log_error
    async def upsert_mama_config(
            self,
            chat_id: int,
            bot_name: str,
            child_user_id: int,
            child_first_name: str,
            gender: str
    ) -> None:
        """Создает или обновляет конфигурацию для бота в конкретном чате."""
        await self._execute(
            queries.UPSERT_MAMA_CONFIG,
            params=(chat_id, bot_name, child_user_id, child_first_name, gender),
            mode='execute'
        )
        logger.info(f"Конфигурация для чата {chat_id} успешно сохранена/обновлена.")

    @log_error
    async def get_mama_config(self, chat_id: int) -> dict | None:
        """Получает активную конфигурацию для бота из конкретного чата."""
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

    @log_error
    async def delete_mama_config(self, chat_id: int) -> int:
        """Удаляем конфигурация для конкретного чата.
        Возвращает количество удаленных строк (0 или 1).
        """
        deleted_rows = await self._execute(
            queries.DELETE_MAMA_CONFIG,
            params=(chat_id,),
            mode='execute'
        )
        if deleted_rows > 0:
            logger.info(f"Конфигурация для чата {chat_id} удалена.")
        else:
            logger.warning(f"Попытка удаления конфигурации для чата {chat_id}, но она не найдена.")
        return deleted_rows



import logging
import asyncpg
import asyncio
from asyncpg import Pool
from contextlib import asynccontextmanager
from core.logging_config import log_error
from core.exceptions import PoolConnectionError

logger = logging.getLogger(__name__)


class PostgresPool:
    """Создает и управляет пулом подключений к PostgreSQL: создание, проверка, отключение."""
    _POOL_MIN_SIZE: int = 1
    _POOL_MAX_SIZE: int = 10
    _DEFAULT_COMMAND_TIMEOUT_SECONDS: float = 5.0
    _CONNECT_RETRY_ATTEMPTS: int = 3
    _CONNECT_RETRY_DELAY_SECONDS: int = 1

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Pool | None = None
        self._is_connected = False
        logger.info(f"PostgresPool инициализирован.")

    @property
    @log_error
    def is_connected(self) -> bool:
        return self._pool is not None and self._is_connected

    @log_error
    async def create_pool(self) -> None:
        """Создает пул подключение к db."""
        if self.is_connected:
            raise PoolConnectionError("Пул уже создан. Необходимо закрыть пул, для создание нового.")

        for attempt in range(self._CONNECT_RETRY_ATTEMPTS):
            try:
                self._pool = None
                self._pool = await asyncpg.create_pool(
                    dsn=self._dsn,
                    min_size=self._POOL_MIN_SIZE,
                    max_size=self._POOL_MAX_SIZE,
                    command_timeout=self._DEFAULT_COMMAND_TIMEOUT_SECONDS
                )
                async with self._pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    logger.info("Успешное подключение к пулу.")
                    self._is_connected = True
                    return
            except (asyncpg.PostgresError, OSError) as e:
                if attempt < self._CONNECT_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(self._CONNECT_RETRY_DELAY_SECONDS)
                else:
                    self._pool = None
                    self._is_connected = False
                    raise PoolConnectionError(f"Попытка подключения {attempt + 1} провалилась: {e}") from e
            except Exception as e:
                if attempt < self._CONNECT_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(self._CONNECT_RETRY_DELAY_SECONDS)
                else:
                    self._pool = None
                    self._is_connected = False
                    raise PoolConnectionError(
                        f"Непредвиденная ошибка на попытке подключения {attempt + 1}: {e}") from e

    @asynccontextmanager
    @log_error
    async def acquire(self, timeout: float | None = None):
        timeout = timeout or self._DEFAULT_COMMAND_TIMEOUT_SECONDS
        if not self.is_connected:
            raise PoolConnectionError("Пул не инициализирован")

        try:
            async with self._pool.acquire(timeout=timeout) as conn:
                yield conn
        except asyncio.TimeoutError as e:
            raise PoolConnectionError("Операция с подключением к пулу завершилась по таймауту.") from e



    @log_error
    async def disconnect(self) -> None:
        """Закрывает подключения к пулу."""
        if not self.is_connected:
            logger.warning("Попытка закрытия пула невозможна, он уже закрыт или не инициализирован.")
            return

        try:
            logger.info("Инициализация закрытия пула подключения к базе данных.")
            await self._pool.close()
            logger.info("Пул подключения к базе данных успешно закрыт.")
        finally:
            # Сбрасываем состояние всегда, чтобы избежать рассинхронизации
            self._is_connected = False
            self._pool = None

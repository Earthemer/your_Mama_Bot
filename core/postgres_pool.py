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

    def __init__(self, dsn: str, **params: dict):
        self._dsn = dsn
        self.pool_min_size = params.get('POOL_MIN_SIZE', 1)
        self.pool_max_size = params.get('POOL_MAX_SIZE', 10)
        self.command_timeout_seconds = params.get('DEFAULT_COMMAND_TIMEOUT_SECONDS', 3)
        self.connect_retry_attempts = params.get('CONNECT_RETRY_ATTEMPTS', 3)
        self.connect_retry_delay_seconds = params.get('CONNECT_RETRY_DELAY_SECONDS', 1)
        self._pool: Pool | None = None
        self._is_connected = False
        logger.info(f"PostgresPool инициализирован.")

    @property
    def is_connected(self) -> bool:
        return self._pool is not None and self._is_connected

    @log_error
    async def create_pool(self) -> None:
        """Создает пул подключение к db."""
        if self.is_connected:
            raise PoolConnectionError("Пул уже создан. Необходимо закрыть пул, для создание нового.")

        for attempt in range(self.connect_retry_attempts):
            try:
                self._pool = None
                self._pool = await asyncpg.create_pool(
                    dsn=self._dsn,
                    min_size=self.pool_min_size,
                    max_size=self.pool_max_size,
                    command_timeout=self.command_timeout_seconds
                )
                async with self._pool.acquire() as conn:
                    await conn.execute("SELECT 1")
                    logger.info("Успешное подключение к пулу.")
                    self._is_connected = True
                    return
            except (asyncpg.PostgresError, OSError) as e:
                if attempt < self.connect_retry_attempts - 1:
                    await asyncio.sleep(self.connect_retry_delay_seconds)
                else:
                    self._pool = None
                    self._is_connected = False
                    raise PoolConnectionError(f"Попытка подключения {attempt + 1} провалилась: {e}ц") from e
            except Exception as e:
                if attempt < self.connect_retry_attempts - 1:
                    await asyncio.sleep(self.connect_retry_delay_seconds)
                else:
                    self._pool = None
                    self._is_connected = False
                    raise PoolConnectionError(
                        f"Непредвиденная ошибка на попытке подключения {attempt + 1}: {e}") from e

    @asynccontextmanager
    async def acquire(self, timeout: float | None = None):
        timeout = timeout or self.command_timeout_seconds
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

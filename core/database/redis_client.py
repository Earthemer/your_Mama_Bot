import logging
import json

from redis.asyncio import Redis, ConnectionPool
from contextlib import asynccontextmanager

from core.exceptions import RedisConnectionError
from core.logging_config import log_error

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Асинхронный клиент для работы с Redis.
    Поддерживает очереди и состояние (hash).
    """
    def __init__(self, host: str, port: int):
        self._pool = ConnectionPool(host=host, port=port, db=0, decode_responses=True)
        self._client: Redis | None = None

    @log_error
    async def connect(self):
        """Устанавливает соединение с Redis."""
        try:
            self._client = Redis(connection_pool=self._pool)
            await self._client.ping()
            logger.info("Успешное подключение к Redis.")
        except Exception as e:
            raise RedisConnectionError(f"Не удалось подключиться к Redis: {e}")

    @log_error
    async def disconnect(self):
        """Закрывает соединение с Redis."""
        if self._client:
            await self._client.close()
            await self._pool.disconnect()
            logger.info("Соединение с Redis закрыто.")

    @asynccontextmanager
    async def lifecycle(self):
        """
        Контекстный менеджер для автоподключения/отключения:
        async with client.lifecycle() as c:
            ...
        """
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()

    # ============ Очередь ============
    @log_error
    async def enqueue(self, queue_name: str, item: dict):
        await self._client.rpush(queue_name, json.dumps(item))

    @log_error
    async def dequeue(self, queue_name: str, timeout: int = 0) -> dict | None:
        result = await self._client.blpop([queue_name], timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    # ============ Состояния ============
    @log_error
    async def set_state(self, key: str, state_data: dict, ttl_seconds: int | None = None):
        await self._client.hset(key, mapping=state_data)
        if ttl_seconds:
            await self._client.expire(key, ttl_seconds)

    @log_error
    async def get_state(self, key: str) -> dict[str, str]:
        return await self._client.hgetall(key)

    @log_error
    async def delete(self, key: str):
        await self._client.delete(key)
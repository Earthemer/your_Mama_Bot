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
    Поддерживает очереди, состояния (hash) и флаги (ключи).
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
        """Добавляет элемент в конец очереди."""
        await self._client.rpush(queue_name, json.dumps(item))

    @log_error
    async def dequeue(self, queue_name: str, timeout: int = 0) -> dict | None:
        """Извлекает элемент из начала очереди (блокирующе)."""
        result = await self._client.blpop([queue_name], timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    @log_error
    async def get_queue_size(self, queue_name: str) -> int:
        """Возрващает текущий размер очереди."""
        return await self._client.llen(queue_name)

    @log_error
    async def get_and_clear_batch(self, queue_name: str) -> list[dict]:
        """Атомарно забирает все элементы из очереди и удаляет ее."""
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.lrange(queue_name, 0, -1)
            pipe.delete(queue_name)
            raw_items, _ = await pipe.execute()

        return [json.loads(item) for item in raw_items]

    @log_error
    async def trim_queue(self, queue_name: str, max_len: int):
        """Обрезает очередь, оставляя последние max_len элементов."""
        await self._client.ltrim(queue_name, -max_len, -1)

    # ============ Состояния ============
    @log_error
    async def set_state(self, key: str, state_data: dict, ttl_seconds: int | None = None):
        """Сохраняет словарь в hash с опциональным TTL."""
        await self._client.hset(key, mapping=state_data)
        if ttl_seconds:
            await self._client.expire(key, ttl_seconds)

    @log_error
    async def get_state(self, key: str) -> dict[str, str]:
        """Возвращает hash-объект."""
        return await self._client.hgetall(key)

    @log_error
    async def set_mode(self, config_id: int, mode: str):
        """Устанавливает текущий режим работы для конкретного чата."""
        key = f"mode:{config_id}"
        await self._client.set(key, mode)

    @log_error
    async def get_mode(self, config_id: int) -> str | None:
        """Получает текущий режим работы для чата."""
        key = f"mode:{config_id}"
        return await self._client.get(key)

    # ============ Флаги ============
    @log_error
    async def set_flag(self, key: str, value: bool, ttl_seconds: int | None = None):
        """Устанавливает булев флаг (True/False)."""
        val = "1" if value else "0"
        await self._client.set(key, val, ex=ttl_seconds)

    @log_error
    async def get_flag(self, key: str) -> bool:
        """Получает булев флаг. По умолчанию False."""
        val = await self._client.get(key)
        return val == "1" if val is not None else False

    @log_error
    async def delete(self, key: str):
        """Удаляет ключ (любого типа)."""
        await self._client.delete(key)

    @log_error
    async def increment_counter(self, key: str, ttl_seconds: int | None = None) -> int:
        """Атомарно увеличивает счетчик и возвращает его новое значение."""
        async with self._client.pipeline() as pipe:
            pipe.incr(key)
            if ttl_seconds:
                pipe.expire(key, ttl_seconds, nx=True)
            results = await pipe.execute()
        return results[0]

    @log_error
    async def set_json(self, key: str, data: dict, ttl_seconds: int | None = None):
        """Сериализует dict в JSON и сохраняет в Redis."""
        await self._client.set(key, json.dumps(data), ex=ttl_seconds)

    @log_error
    async def get_json(self, key: str) -> dict | None:
        """Получает строку из Redis и десериализует ее из JSON."""
        raw_data = await self._client.get(key)
        if raw_data:
            return json.loads(raw_data)
        return None

    @log_error
    async def set_string(self, key: str, value: str, ttl_seconds: int | None = None):
        """Сохраняет строковое значение в Redis."""
        await self._client.set(key, value, ex=ttl_seconds)

    @log_error
    async def get_string(self, key: str) -> str | None:
        """Возвращает строковое значение из Redis (или None)."""
        return await self._client.get(key)
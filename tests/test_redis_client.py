import pytest
import pytest_asyncio

from typing import AsyncGenerator

from core.database.redis_client import RedisClient
from core.config.parameters import REDIS_PORT, REDIS_HOST

@pytest.fixture
async def redis_client() -> AsyncGenerator[RedisClient, None]:
    """Фикстура, которая создает и очищает клиент для каждого теста."""
    client = RedisClient(host=REDIS_HOST, port=REDIS_PORT)
    async with client.lifecycle():
        await client._client.flushdb()
        yield client


async def test_enqueue_and_dequeue(redis_client: RedisClient):
    """
    Тест: проверяем, что мы можем положить в очередь словарь и получить его обратно.
    """
    # --- ARRANGE ---
    queue_name = "test_queue"
    test_item = {"user_id": 123, "text": "hello"}

    # --- ACT ---
    # 1. Кладем элемент в очередь
    await redis_client.enqueue(queue_name, test_item)

    # 2. Достаем элемент из очереди
    retrieved_item = await redis_client.dequeue(queue_name, timeout=1)

    # --- ASSERT ---
    assert retrieved_item is not None
    assert isinstance(retrieved_item, dict)
    assert retrieved_item["user_id"] == 123
    assert retrieved_item["text"] == "hello"


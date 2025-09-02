import pytest


from typing import AsyncGenerator
from unittest.mock import AsyncMock

from core.database.redis_client import RedisClient
from core.config.parameters import REDIS_PORT, REDIS_HOST


@pytest.fixture
async def redis_client() -> AsyncGenerator[RedisClient, None]:
    """Фикстура, которая создает и очищает клиент для каждого теста."""
    client = RedisClient(host=REDIS_HOST, port=REDIS_PORT)
    async with client.lifecycle():
        await client._client.flushdb()
        yield client


async def test_exception_connect_error(mocker, redis_client):
    mocker.patch.object(redis_client, "connect", AsyncMock(side_effect=Exception("Что-то совсем непредвиденное")))

    with pytest.raises(Exception, match="Что-то совсем непредвиденное"):
        async with redis_client.lifecycle():
            pass


async def test_enqueue_and_dequeue(redis_client: RedisClient):
    """
    Тест: проверяем, что мы можем положить в очередь словарь и получить его обратно.
    """
    queue_name = "test_queue"
    test_item = {"user_id": 123, "text": "hello"}

    await redis_client.enqueue(queue_name, test_item)

    retrieved_item = await redis_client.dequeue(queue_name, timeout=1)

    assert retrieved_item is not None
    assert isinstance(retrieved_item, dict)
    assert retrieved_item["user_id"] == 123
    assert retrieved_item["text"] == "hello"


async def test_get_queue_size_and_get_clear_batch(redis_client: RedisClient):
    queue = "test_multi"
    items = [
        {"user_id": 1, "text": "a"},
        {"user_id": 2, "text": "b"},
        {"user_id": 3, "text": "c"},
    ]

    for item in items:
        await redis_client.enqueue(queue, item)

    size = await redis_client.get_queue_size(queue)
    assert size == len(items)

    result = await redis_client.get_and_clear_batch(queue)

    assert result == items or result == list(reversed(items))

    retrieved_item = await redis_client.dequeue(queue, timeout=1)
    assert retrieved_item is None

async def test_trim_queue(redis_client: RedisClient):
    queue = "test_trim"
    for i in range(5):
        await redis_client.enqueue(queue, {"n": i})
    await redis_client.trim_queue(queue, max_len=2)
    size = await redis_client.get_queue_size(queue)
    assert size == 2
    result = await redis_client.get_and_clear_batch(queue)
    assert result == [{"n": 3}, {"n": 4}]

async def test_set_and_get_state(redis_client: RedisClient):
    key = "state:123"
    state = {"a": "1", "b": "2"}
    await redis_client.set_state(key, state)
    result = await redis_client.get_state(key)
    assert result == state

async def test_set_and_get_mode(redis_client: RedisClient):
    config_id = 42
    await redis_client.set_mode(config_id, "active")
    result = await redis_client.get_mode(config_id)
    assert result == "active"

async def test_set_and_get_flag(redis_client: RedisClient):
    key = "flag:test"
    await redis_client.set_flag(key, True)
    assert await redis_client.get_flag(key) is True
    await redis_client.set_flag(key, False)
    assert await redis_client.get_flag(key) is False

async def test_delete(redis_client: RedisClient):
    key = "to_delete"
    await redis_client.set_mode(99, "temp")
    await redis_client.delete(f"mode:99")
    result = await redis_client.get_mode(99)
    assert result is None

async def test_increment_counter(redis_client: RedisClient):
    key = "counter:test"
    value1 = await redis_client.increment_counter(key)
    value2 = await redis_client.increment_counter(key)
    assert value1 == 1
    assert value2 == 2

import pytest
import pytest_asyncio
import datetime

from fakeredis.aioredis import FakeRedis
from unittest.mock import AsyncMock, MagicMock
from typing import Any, AsyncGenerator
from aiogram import types

from core.config.parameters import ONLINE_MODE_BATCH_THRESHOLD, ONLINE_MODE_REPLY_LIMIT
from core.brain_service import BrainService
from core.operator import Operator
from core.database.redis_client import RedisClient


# фикстуры
@pytest_asyncio.fixture(scope='function')
async def redis_client() -> AsyncGenerator[RedisClient, Any]:
    """
    Создает RedisClient, привязанный к fake Redis.
    - Каждая фикстура с "function" scope имеет чистую БД.
    - flushdb очищает все ключи перед и после теста.
    """
    fake_redis_instance = await FakeRedis(decode_responses=True)
    client = RedisClient(host='localhost', port=6379)
    client._pool = fake_redis_instance.connection_pool
    client._client = fake_redis_instance

    await client._client.flushdb()
    yield client
    await client._client.flushdb()


@pytest.fixture(scope="function")
def brain_service_mock() -> MagicMock:
    """Создаём мок BrainService напрямую."""
    instance = MagicMock(spec=BrainService)
    instance.process_single_message_immediately = AsyncMock()
    instance.process_online_batch = AsyncMock()
    instance.say_goodbye_and_switch_to_passive = AsyncMock()
    return instance


@pytest.fixture
def operator(redis_client, brain_service_mock) -> Operator:
    """Фикстура, создающая 'боевой' инстанс Operator с нашими тестовыми зависимостями."""
    return Operator(redis_client, brain_service_mock)


@pytest.fixture(scope="session")
def test_config() -> dict:
    """Возвращает стандартный словарь конфигурации."""
    return {
        "id": 1,
        "chat_id": -100123456789,
        "bot_name": "Мама",
        "child_participant_id": 10
    }


@pytest.fixture(scope="session")
def test_participant() -> dict:
    """Возвращает стандартный словарь участника."""
    return {
        "id": 11,
        "user_id": 555666777,
        "custom_name": "Петя",
        "relationship_score": 50
    }


@pytest.fixture(scope="session")
def test_child_participant() -> dict:
    """Возвращает словарь участника, который является 'ребенком'."""
    return {
        "id": 10,
        "user_id": 111222333,
        "custom_name": "Леша",
        "relationship_score": 75
    }


# --- Фикстуры, имитирующие объекты aiogram
@pytest.fixture
def background_message(test_participant, test_config) -> MagicMock:
    """Сообщение — обычный фоновый шум."""
    message = MagicMock(spec=types.Message)

    from_user = MagicMock(spec=types.User)
    from_user.is_bot = False
    from_user.id = test_participant['user_id']
    message.from_user = from_user

    chat = MagicMock(spec=types.Chat)
    chat.id = test_config['chat_id']
    message.chat = chat

    message.text = "Сегодня хорошая погода?"
    message.date = datetime.datetime.utcnow()
    message.reply_to_message = None

    return message


@pytest.fixture
def direct_mention_message(test_participant, test_config) -> MagicMock:
    """Сообщение с прямым упоминанием 'Мамы'."""
    message = MagicMock(spec=types.Message)

    from_user = MagicMock(spec=types.User)
    from_user.is_bot = False
    from_user.id = test_participant['user_id']
    message.from_user = from_user

    chat = MagicMock(spec=types.Chat)
    chat.id = test_config['chat_id']
    message.chat = chat

    message.text = "Мама, а что на ужин?"
    message.date = datetime.datetime.utcnow()
    message.reply_to_message = None

    return message


@pytest.fixture
def child_message(test_child_participant, test_config) -> MagicMock:
    """Сообщение от 'ребенка'."""
    message = MagicMock(spec=types.Message)

    from_user = MagicMock(spec=types.User)
    from_user.is_bot = False
    from_user.id = test_child_participant['user_id']
    message.from_user = from_user

    chat = MagicMock(spec=types.Chat)
    chat.id = test_config['chat_id']
    message.chat = chat

    message.text = "Мам, я шапку надел."
    message.date = datetime.datetime.utcnow()
    message.reply_to_message = None

    return message


# ----- Тесты FakeRedis

@pytest.mark.asyncio
async def test_redis_enqueue_and_size(redis_client):
    queue_name = "test_queue"
    payload = {"text": "Привет"}

    size = await redis_client.get_queue_size(queue_name)
    assert size == 0

    await redis_client.enqueue(queue_name, payload)

    size = await redis_client.get_queue_size(queue_name)
    assert size == 1

    item = await redis_client.dequeue(queue_name)
    assert item["text"] == "Привет"

    size = await redis_client.get_queue_size(queue_name)
    assert size == 0


@pytest.mark.asyncio
async def test_set_and_get_mode(redis_client):
    chat_id = 123
    mode = 'GATHERING'

    await redis_client.set_mode(chat_id, mode)

    retrieved_mode = await redis_client.get_mode(chat_id)

    assert retrieved_mode == mode


# ---- Тесты Operator
async def test_gathering_direct_mention_goes_to_direct_queue(redis_client, operator, brain_service_mock, test_config,
                                                             test_participant,
                                                             direct_mention_message):
    await redis_client.set_mode(test_config['id'], 'GATHERING')
    direct_queue = f"direct_queue:{test_config['id']}"
    background_queue = f"background_queue:{test_config['id']}"

    await operator.handle_message(direct_mention_message, test_config, test_participant)

    assert await redis_client.get_queue_size(direct_queue) == 1
    assert await redis_client.get_queue_size(background_queue) == 0
    brain_service_mock.assert_not_called()


async def test_gathering_background_noise_goes_to_background_queue(redis_client, operator, brain_service_mock,
                                                                   test_config,
                                                                   test_participant,
                                                                   background_message):
    await redis_client.set_mode(test_config['id'], 'GATHERING')
    direct_queue = f"direct_queue:{test_config['id']}"
    background_queue = f"background_queue:{test_config['id']}"

    await operator.handle_message(background_message, test_config, test_participant)
    assert await redis_client.get_queue_size(direct_queue) == 0
    assert await redis_client.get_queue_size(background_queue) == 1
    brain_service_mock.assert_not_called()


async def test_passive_child_message_is_queued(
        operator, redis_client, brain_service_mock, test_config, test_child_participant, child_message
):
    await redis_client.set_mode(test_config['id'], "PASSIVE")
    direct_queue = f"direct_queue:{test_config['id']}"

    await operator.handle_message(child_message, test_config, test_child_participant)

    assert await redis_client.get_queue_size(direct_queue) == 1
    brain_service_mock.process_single_message_immediately.assert_not_called()


async def test_passive_mention_with_successful_roll(
        operator, redis_client, brain_service_mock, mocker, test_config, test_participant, direct_mention_message
):
    await redis_client.set_mode(test_config['id'], 'PASSIVE')
    mocker.patch('core.operator.random.randint', return_value=1)

    await operator.handle_message(direct_mention_message, test_config, test_participant)

    assert await redis_client.get_queue_size(f"direct_queue:{test_config['id']}") == 0
    brain_service_mock.process_single_message_immediately.assert_called_once()


async def test_passive_mention_with_failed_roll(
        operator, redis_client, brain_service_mock, mocker, test_config, test_participant, direct_mention_message
):
    await redis_client.set_mode(test_config['id'], 'PASSIVE')
    mocker.patch('core.operator.random.randint', return_value=100)

    await operator.handle_message(direct_mention_message, test_config, test_participant)
    assert await redis_client.get_queue_size(f"direct_queue:{test_config['id']}") == 0
    brain_service_mock.process_single_message_immediately.assert_not_called()


async def test_online_batch_trigger_fires_on_threshold(
        operator, redis_client, brain_service_mock, test_config, test_participant, background_message, mocker
):
    await redis_client.set_mode(test_config['id'], 'ONLINE')

    mocker.patch.object(redis_client, "get_flag", return_value=False)
    mocker.patch.object(redis_client, "set_flag", return_value=True)

    for _ in range(ONLINE_MODE_BATCH_THRESHOLD - 1):
        await operator.handle_message(background_message, test_config, test_participant)
        brain_service_mock.process_online_batch.assert_not_called()

    await operator.handle_message(background_message, test_config, test_participant)

    await redis_client.get_queue_size(f"online_batch_queue:{test_config['id']}")

    brain_service_mock.process_online_batch.assert_called_once_with(test_config['id'])


async def test_online_reply_limit_is_respected(
        operator, redis_client, brain_service_mock, test_config, test_participant, background_message
):
    # Устанавливаем режим ONLINE
    await redis_client.set_mode(test_config['id'], 'ONLINE')

    counter_key = f"online_replies_count:{test_config['id']}"
    for _ in range(ONLINE_MODE_REPLY_LIMIT):
        await redis_client.increment_counter(counter_key)

    await operator.handle_message(background_message, test_config, test_participant)

    brain_service_mock.process_online_batch.assert_not_called()

    brain_service_mock.say_goodbye_and_switch_to_passive.assert_called_once_with(test_config['id'])


async def test_online_user_cooldown_works(
        operator, redis_client, brain_service_mock, test_config, test_participant, background_message
):
    await redis_client.set_mode(test_config['id'], 'ONLINE')
    config_id = test_config['id']
    user_id = test_participant['user_id']

    await operator.handle_message(background_message, test_config, test_participant)

    cooldown_key = f"online_user_cooldown:{config_id}:{user_id}"
    flag = await redis_client.get_flag(cooldown_key)
    assert flag is True

    await operator.handle_message(background_message, test_config, test_participant)

    batch_queue = f"online_batch_queue:{config_id}"
    size = await redis_client.get_queue_size(batch_queue)
    assert size == 1

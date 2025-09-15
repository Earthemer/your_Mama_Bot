import pytest

from unittest.mock import AsyncMock, MagicMock

from aiogram import Bot

from tests.test_operator import redis_client, test_config, test_participant, background_message
from handlers.listener import message_listener
from core.database.postgres_client import AsyncPostgresManager
from core.operator_messages import Operator


# ---- Фикстуры
@pytest.fixture
def db_manager_mock() -> AsyncMock:
    """Мок для AsyncPostgresManager."""
    mock = AsyncMock(spec=AsyncPostgresManager)

    mock.get_mama_config.return_value = None
    mock.get_participant.return_value = None
    return mock


@pytest.fixture
def operator_mock() -> AsyncMock:
    """Мок для Operator."""
    mock = AsyncMock(spec=Operator)
    return mock


@pytest.fixture
def bot_mock() -> MagicMock:
    """Мок для объекта aiogram.Bot."""
    mock = MagicMock(spec=Bot)
    mock.id = 123456789
    return mock

# ---- Тесты
@pytest.mark.asyncio
async def test_listener_cold_cache(
        redis_client, db_manager_mock, operator_mock, bot_mock, test_config, test_participant, background_message
):
    db_manager_mock.get_mama_config.return_value = test_config
    db_manager_mock.get_participant.return_value = test_participant

    chat_id = test_config['chat_id']
    config_exists_key = f"config_exists:{chat_id}"
    config_data_key = f"config_data:{chat_id}"

    await message_listener(
        message=background_message,
        db=db_manager_mock,
        redis=redis_client,
        operator=operator_mock,
        bot=bot_mock
    )

    db_manager_mock.get_mama_config.assert_called_once_with(chat_id)
    assert await redis_client.get_flag(config_exists_key) is True
    assert await redis_client.get_json(config_data_key) == test_config
    operator_mock.handle_message.assert_called_once_with(
        message=background_message,
        config=test_config,
        participant=test_participant
    )

@pytest.mark.asyncio
async def test_listener_hot_cache(
        redis_client, db_manager_mock, operator_mock, bot_mock, test_config, test_participant, background_message
):
    """
    Тестируем "счастливый путь" с горячим кэшем.
    Ожидаем: 0 запросов в БД за конфигом, данные берутся из Redis, вызов оператора.
    """
    chat_id = test_config['chat_id']
    config_exists_key = f"config_exists:{chat_id}"
    config_data_key = f"config_data:{chat_id}"

    await redis_client.set_flag(config_exists_key, True)
    await redis_client.set_json(config_data_key, test_config)

    db_manager_mock.get_participant.return_value = test_participant

    # --- ACT ---
    await message_listener(
        message=background_message,
        db=db_manager_mock,
        redis=redis_client,
        operator=operator_mock,
        bot=bot_mock
    )

    db_manager_mock.get_mama_config.assert_not_called()

    operator_mock.handle_message.assert_called_once_with(
        message=background_message,
        config=test_config,
        participant=test_participant
    )


@pytest.mark.asyncio
async def test_listener_ignores_if_no_config(
        redis_client, db_manager_mock, operator_mock, bot_mock, background_message
):
    await message_listener(
        message=background_message,
        db=db_manager_mock,
        redis=redis_client,
        operator=operator_mock,
        bot=bot_mock
    )

    operator_mock.handle_message.assert_not_called()


@pytest.mark.asyncio
async def test_listener_ignores_ignored_participant(
        redis_client, db_manager_mock, operator_mock, bot_mock, test_config, background_message
):
    # --- ARRANGE ---
    ignored_participant = {"id": 11, "user_id": 555, "is_ignored": True}
    db_manager_mock.get_mama_config.return_value = test_config
    db_manager_mock.get_participant.return_value = ignored_participant

    await message_listener(
        message=background_message,
        db=db_manager_mock,
        redis=redis_client,
        operator=operator_mock,
        bot=bot_mock
    )

    operator_mock.handle_message.assert_not_called()

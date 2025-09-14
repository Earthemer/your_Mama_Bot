import pytest
from unittest.mock import AsyncMock, MagicMock

from core.brain_service import BrainService
from core.config.botmode import BotMode
from core.llm.llm_processor import LLMResponse

from tests.test_operator import redis_client, test_config


@pytest.fixture
def mock_db_manager() -> AsyncMock:
    """Мок для AsyncPostgresManager."""
    mock = AsyncMock()
    mock.get_mama_config_by_id.return_value = {'id': 1, 'chat_id': -1001}
    mock.get_all_participants_by_config_id.return_value = [
        {'id': 10, 'user_id': 123, 'custom_name': 'Тестер'}
    ]
    return mock


@pytest.fixture
def mock_prompt_factory() -> MagicMock:
    """Мок для PromptFactory."""
    return MagicMock()


@pytest.fixture
def mock_llm_processor() -> AsyncMock:
    """Мок для LLMProcessor."""
    mock = AsyncMock()
    mock.process_session_start.return_value = LLMResponse(text_reply="Привет, мир!", data_json=None)
    mock.process_session_message.return_value = LLMResponse(text_reply="Ответ в сессии.", data_json=None)
    mock.process_single.return_value = LLMResponse(text_reply="Одиночный ответ.", data_json=None)
    return mock


@pytest.fixture
def mock_bot() -> AsyncMock:
    """Мок для aiogram.Bot."""
    mock = AsyncMock()
    mock.send_message = AsyncMock()
    return mock


@pytest.fixture
def brain_service(redis_client, mock_db_manager, mock_prompt_factory, mock_llm_processor, mock_bot) -> BrainService:
    """BrainService"""
    return BrainService(
        redis_client=redis_client,
        db_manager=mock_db_manager,
        prompt_factory=mock_prompt_factory,
        llm_processor=mock_llm_processor,
        bot=mock_bot
    )


# --- ТЕСТЫ

@pytest.mark.asyncio
async def test_start_online_interactions_happy_path(brain_service: BrainService, redis_client, test_config):
    await redis_client.enqueue(f"direct_queue:{test_config['id']}", {"text": "Привет, мама"})
    await redis_client.enqueue(f"background_queue:{test_config['id']}", {"text": "Погода норм"})
    await brain_service.start_online_interactions(test_config['id'], "morning")
    brain_service.db.get_mama_config_by_id.assert_awaited_once_with(test_config['id'])
    brain_service.prompts.create_session_start_prompt.assert_called_once()
    brain_service.llm.process_session_start.assert_awaited_once()
    brain_service.bot.send_message.assert_awaited_once_with(
        brain_service.db.get_mama_config_by_id.return_value['chat_id'],
        brain_service.llm.process_session_start.return_value.text_reply
    )


@pytest.mark.asyncio
async def test_start_online_interactions_no_messages_exits_gracefully(brain_service: BrainService, test_config):
    await brain_service.start_online_interactions(test_config['id'], "morning")
    brain_service.llm.process_session_start.assert_not_awaited()
    brain_service.bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_online_batch_happy_path(brain_service: BrainService, redis_client, test_config):
    await redis_client.enqueue(f"online_batch_queue:{test_config['id']}", {"text": "Что нового?"})

    await brain_service.process_online_batch(test_config['id'])

    brain_service.prompts.create_online_prompt.assert_called_once()
    brain_service.llm.process_session_message.assert_awaited_once()
    brain_service.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_single_message_immediately_happy_path(brain_service: BrainService, test_config):

    await brain_service.process_single_message_immediately({"text": "Мама?"}, test_config)

    brain_service.prompts.create_single_reply_prompt.assert_called_once()
    brain_service.llm.process_single.assert_awaited_once()
    brain_service.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_say_goodbye_when_online(brain_service: BrainService, redis_client, test_config):
    await redis_client.set_mode(test_config['id'], BotMode.ONLINE.value)

    await brain_service.say_goodbye_and_switch_to_passive(test_config['id'])

    brain_service.llm.process_session_message.assert_awaited_once()
    brain_service.llm.process_session_end.assert_awaited_once_with(session_id=test_config['id'])
    assert await redis_client.get_mode(test_config['id']) == BotMode.PASSIVE.value
    assert await redis_client.get_string(f"online_replies_count:{test_config['id']}") is None


@pytest.mark.asyncio
async def test_say_goodbye_when_not_online_does_nothing(brain_service: BrainService, redis_client, test_config):
    await redis_client.set_mode(test_config['id'], BotMode.PASSIVE.value)

    await brain_service.say_goodbye_and_switch_to_passive(test_config['id'])

    brain_service.llm.process_session_message.assert_not_awaited()
    brain_service.llm.process_session_end.assert_not_awaited()
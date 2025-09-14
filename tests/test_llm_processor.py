import pytest
from unittest.mock import AsyncMock, MagicMock

from core.llm.llm_processor import LLMProcessor, LLMResponse, LLMError
from core.llm.base_llm_client import BaseLLMClient
from core.config.parameters import Prompt, SessionId


# ---- Фикстуры

@pytest.fixture
def mock_client() -> MagicMock:
    """Мок клиента BaseLLMClient с асинхронными методами."""
    client = MagicMock(spec=BaseLLMClient)
    client.generate_single = AsyncMock()
    client.start_session = AsyncMock()
    client.send_in_session = AsyncMock()
    client.end_session = AsyncMock()
    return client


@pytest.fixture
def llm_processor(mock_client: MagicMock) -> LLMProcessor:
    """Инстанс LLMProcessor с замоканным клиентом."""
    return LLMProcessor(mock_client)


# ---- Тесты process_single

@pytest.mark.asyncio
async def test_process_single_returns_structured_response(llm_processor: LLMProcessor, mock_client: MagicMock):
    prompt = {"text": "Привет"}
    mock_client.generate_single.return_value = "Ответ LLM"

    response = await llm_processor.process_single(prompt)

    assert isinstance(response, LLMResponse)
    assert response.text_reply == "Ответ LLM"
    assert response.data_json is None
    mock_client.generate_single.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_single_with_json_in_response(llm_processor: LLMProcessor, mock_client: MagicMock):
    prompt = {"text": "Привет"}
    mock_client.generate_single.return_value = 'Текст ответа===JSON==={"key":123}'

    response = await llm_processor.process_single(prompt)

    assert response.text_reply == "Текст ответа"
    assert response.data_json == {"key": 123}


@pytest.mark.asyncio
async def test_process_single_raises_on_invalid_prompt(llm_processor: LLMProcessor):
    prompt = {"invalid": set([1, 2, 3])}  # set не сериализуется в JSON

    with pytest.raises(LLMError, match="Ошибка сериализации промпт-объекта"):
        await llm_processor.process_single(prompt)


# ---- Тесты process_session_start

@pytest.mark.asyncio
async def test_process_session_start_returns_response(llm_processor: LLMProcessor, mock_client: MagicMock):
    session_id = "session1"
    system_prompt = {"system": "init"}
    mock_client.start_session.return_value = "Старт сессии"

    response = await llm_processor.process_session_start(session_id, system_prompt)

    assert response.text_reply == "Старт сессии"
    assert response.data_json is None
    mock_client.start_session.assert_awaited_once_with(session_id, '{"system":"init"}')


# ---- Тесты process_session_message

@pytest.mark.asyncio
async def test_process_session_message_returns_response(llm_processor: LLMProcessor, mock_client: MagicMock):
    session_id = "sess2"
    prompt = {"text": "сообщение"}
    mock_client.send_in_session.return_value = "Ответ внутри сессии"

    response = await llm_processor.process_session_message(session_id, prompt)

    assert response.text_reply == "Ответ внутри сессии"
    assert response.data_json is None
    mock_client.send_in_session.assert_awaited_once_with(session_id, '{"text":"сообщение"}')


# ---- Тесты process_session_end

@pytest.mark.asyncio
async def test_process_session_end_calls_client_end_session(llm_processor: LLMProcessor, mock_client: MagicMock):
    session_id = "sess3"
    await llm_processor.process_session_end(session_id)
    mock_client.end_session.assert_awaited_once_with(session_id)


# ---- Тесты _parse_response

def test_parse_response_with_non_string_input():
    raw = 12345  # число вместо строки
    response = LLMProcessor._parse_response(raw)
    assert response.text_reply == "12345"
    assert response.data_json is None


def test_parse_response_with_invalid_json_logs_error(caplog):
    raw = 'Текст===JSON==={invalid_json}'
    caplog.set_level("ERROR")
    response = LLMProcessor._parse_response(raw)
    assert response.text_reply.startswith("Текст")
    assert response.data_json is None
    assert any("ОШИБКА ПАРСИНГА" in r.message for r in caplog.records)
import pytest

from unittest.mock import MagicMock
from unittest.mock import ANY
from google.api_core import exceptions as google_exceptions

from core.llm.gemini_client import GeminiClient
from core.config.exceptions import LLMError


# --- Фикстуры

@pytest.fixture
def mock_generative_model() -> MagicMock:
    """Мокает сам genai.GenerativeModel, чтобы не делать реальных вызовов."""
    model_mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Mocked LLM Response"
    model_mock.generate_content.return_value = mock_response

    chat_session_mock = MagicMock()
    chat_session_mock.send_message.return_value = mock_response
    model_mock.start_chat.return_value = chat_session_mock

    return model_mock


@pytest.fixture(autouse=True)
def patch_genai(mocker, mock_generative_model):
    """
    Главный патч. Он подменяет genai.GenerativeModel во всем модуле gemini_client на время теста.
    """
    mocker.patch('core.llm.gemini_client.genai.GenerativeModel', return_value=mock_generative_model)
    mocker.patch('core.llm.gemini_client.genai.configure')


@pytest.fixture
def gemini_client() -> GeminiClient:
    """Создает инстанс GeminiClient с фейковым ключом."""
    return GeminiClient(api_key="fake-api-key")


# --- Тесты

@pytest.mark.asyncio
async def test_generate_single_happy_path(gemini_client: GeminiClient, mock_generative_model: MagicMock):
    prompt = "Тестовый промпт"
    response = await gemini_client.generate_single(prompt)

    assert response == "Mocked LLM Response"
    mock_generative_model.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_generate_single_handles_api_error(gemini_client: GeminiClient, mock_generative_model: MagicMock):
    mock_generative_model.generate_content.side_effect = google_exceptions.GoogleAPICallError("API is down")

    with pytest.raises(LLMError, match="Ошибка API Gemini"):
        await gemini_client.generate_single("промпт")


@pytest.mark.asyncio
async def test_start_session_happy_path(gemini_client: GeminiClient):
    session_id = "sess1"
    prompt = "Системный промпт"

    response = await gemini_client.start_session(session_id, prompt)

    assert response == "Mocked LLM Response"
    assert session_id in gemini_client._session
    assert gemini_client._session[session_id] is not None


@pytest.mark.asyncio
async def test_send_in_session_happy_path(gemini_client: GeminiClient, mock_generative_model: MagicMock):
    session_id = "sess2"
    await gemini_client.start_session(session_id, "init")

    response = await gemini_client.send_in_session(session_id, "сообщение")

    assert response == "Mocked LLM Response"
    chat_session_mock = mock_generative_model.start_chat.return_value
    chat_session_mock.send_message.assert_called_with(content="сообщение", generation_config=ANY, safety_settings=ANY)

@pytest.mark.asyncio
async def test_send_in_nonexistent_session_raises_error(gemini_client: GeminiClient):
    with pytest.raises(LLMError, match="несуществующую сессию"):
        await gemini_client.send_in_session("bad_session_id", "сообщение")

@pytest.mark.asyncio
async def test_end_session_removes_session(gemini_client: GeminiClient):
    session_id = "sess3"
    await gemini_client.start_session(session_id, "init")
    assert session_id in gemini_client._session

    await gemini_client.end_session(session_id)

    assert session_id not in gemini_client._session

@pytest.mark.asyncio
async def test_end_session_is_idempotent(gemini_client: GeminiClient):
    try:
        await gemini_client.end_session("nonexistent_session")
    except Exception as e:
        pytest.fail(f"end_session кинул ошибку на несуществующей сессии: {e}")
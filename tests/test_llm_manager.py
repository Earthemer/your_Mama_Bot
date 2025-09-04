import pytest
from unittest.mock import MagicMock, AsyncMock

from pygments.lexer import default

from core.llm_manager import LLMManager
from core.exceptions import LLMError

# ---- Фикстуры
@pytest.fixture
def llm_manager() -> LLMManager:
    """Создает инстанс LLMManager с фейковым API-ключом для тестов."""
    return LLMManager(api_key='fake-api-key')


@pytest.fixture
def mock_genai_client(mocker) -> MagicMock:
    """
    Мокает клиент google-genai, чтобы избежать реальных API-вызовов.
    Возвращает сам мок клиента для дальнейшей настройки в тестах.
    """
    mock_client = mocker.patch('core.llm_manager.genai.Client')
    return mock_client

# ---- Тесты

@pytest.mark.asyncio
async def test_get_raw_response_success(llm_manager: LLMManager, mocker: MagicMock):
    expected_text = "Это тестовый ответ от LLM."
    mock_response = MagicMock()
    mock_response.text = expected_text

    mock_to_thread = mocker.patch('core.llm_manager.to_thread', new_callable=AsyncMock)
    mock_to_thread.return_value = mock_response

    result = await llm_manager.get_raw_response("Тест промпт.")
    assert result == expected_text
    mock_to_thread.assert_called_once()

@pytest.mark.asyncio
async def test_get_raw_response_raises_error_on_empty_text(llm_manager: LLMManager, mocker: MagicMock):
    mock_response = MagicMock()
    mock_response.text = None
    mock_to_thread = mocker.patch('core.llm_manager.to_thread', new_callable=AsyncMock)
    mock_to_thread.return_value = mock_response

    with pytest.raises(LLMError, match="Модель не вернула текстовый ответ."):
        await llm_manager.get_raw_response("Тестовый промпт")

@pytest.mark.asyncio
async def test_get_raw_response_handles_api_exception(llm_manager: LLMManager, mocker: MagicMock):
    error_message = "Ошибка выполнения в потоке"
    mock_to_thread = mocker.patch('core.llm_manager.to_thread', new_callable=AsyncMock)
    mock_to_thread.side_effect = Exception(error_message)

    with pytest.raises(LLMError, match="Не удалось получить ответ от нейросети."):
        await llm_manager.get_raw_response("Тестовый промпт")
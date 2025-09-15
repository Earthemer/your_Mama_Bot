import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, CallbackQuery

from handlers.common import handle_start, handle_clean, cancel_dialog
from core.database.postgres_client import AsyncPostgresManager

# ---- Фикстуры
@pytest.fixture
def mock_message():
    msg = AsyncMock(spec=Message)

    user = MagicMock()
    user.id = 123
    msg.from_user = user

    chat = MagicMock()
    chat.id = 100
    chat.type = "group"
    msg.chat = chat

    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.delete = AsyncMock()

    bot = MagicMock()
    bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))
    msg.bot = bot

    return msg

@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncPostgresManager)
    db.get_mama_config = AsyncMock(return_value=None)
    db.delete_mama_config = AsyncMock(return_value=1)
    return db

@pytest.fixture
def mock_callback():
    cb = AsyncMock(spec=CallbackQuery)

    user = MagicMock()
    user.id = 123
    cb.from_user = user
    msg = AsyncMock(spec=Message)
    chat = MagicMock()
    chat.id = 100
    chat.type = "group"
    msg.chat = chat
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    msg.delete = AsyncMock()
    cb.message = msg

    cb.answer = AsyncMock()
    return cb

@pytest.fixture
def mock_state():
    state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)
    state.clear = AsyncMock()
    return state

# ---- Тесты
@pytest.mark.asyncio
async def test_handle_start_no_config(mock_message, mock_db):
    mock_db.get_mama_config.return_value = None
    await handle_start(mock_message, mock_db)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_handle_start_with_config(mock_message, mock_db):
    mock_db.get_mama_config.return_value = {"bot_name": "Мама"}
    await handle_start(mock_message, mock_db)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_handle_clean_success(mock_message, mock_db):
    mock_db.delete_mama_config.return_value = 1
    await handle_clean(mock_message, mock_db)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_handle_clean_no_config(mock_message, mock_db):
    mock_db.delete_mama_config.return_value = 0
    await handle_clean(mock_message, mock_db)
    mock_message.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_dialog_no_state(mock_callback, mock_state):
    mock_state.get_state.return_value = None
    await cancel_dialog(mock_callback, mock_state)
    mock_callback.message.delete.assert_called_once()
    mock_callback.answer.assert_called_once()

@pytest.mark.asyncio
async def test_cancel_dialog_with_state(mock_callback, mock_state):
    mock_state.get_state.return_value = "some_state"
    await cancel_dialog(mock_callback, mock_state)
    mock_state.clear.assert_called_once()
    mock_callback.answer.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()
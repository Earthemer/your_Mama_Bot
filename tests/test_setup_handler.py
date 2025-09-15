import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Chat, User, Message

from handlers.setup_dialog import (
    start_setup_dialog, get_mama_name, get_timezone,
    choose_child, get_child_name, set_gender_and_finish
)
from core.database.postgres_client import AsyncPostgresManager


# ---- Фикстуры для FSM и базы
@pytest.fixture
def mock_state():
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={"admin_id": 123})
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncPostgresManager)
    db.upsert_mama_config.return_value = 1
    db.add_participant.return_value = {"id": 42}
    db.set_child = AsyncMock()
    db.update_personality_prompt = AsyncMock()
    return db


# ---- Фикстура для Message
@pytest.fixture
def mock_message():
    msg = AsyncMock(spec=Message)

    user = MagicMock(spec=User)
    user.id = 123
    msg.from_user = user

    chat = MagicMock(spec=Chat)
    chat.id = 100
    chat.type = "group"
    msg.chat = chat

    msg.reply_to_message = None

    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()

    return msg

@pytest.fixture
def mock_personality_manager():
    pm = AsyncMock()
    pm.get_random_personality = MagicMock(return_value={"name": "Веселый", "prompt": "Будь веселым"})
    return pm


# ---- Фикстура для CallbackQuery
@pytest.fixture
def mock_callback():
    cb = AsyncMock(spec=CallbackQuery)

    user = MagicMock(spec=User)
    user.id = 123
    cb.from_user = user

    msg = AsyncMock(spec=Message)
    chat = MagicMock(spec=Chat)
    chat.id = 100
    chat.type = "group"
    msg.chat = chat
    msg.edit_text = AsyncMock()
    msg.answer = AsyncMock()
    cb.message = msg

    cb.answer = AsyncMock()

    cb.data = "tz_UTC+3"

    cb.bot.get_chat_member = AsyncMock(return_value=MagicMock(status="administrator"))

    return cb


# ---- Тесты
@pytest.mark.asyncio
async def test_start_setup_dialog_group(mock_callback, mock_state):
    result = await start_setup_dialog(mock_callback, mock_state)
    mock_callback.message.edit_text.assert_called_once()
    assert result is None


@pytest.mark.asyncio
async def test_get_mama_name_valid(mock_message, mock_state):
    mock_message.text = "Мама"
    await get_mama_name(mock_message, mock_state)
    mock_state.update_data.assert_called()
    mock_message.answer.assert_called()


@pytest.mark.asyncio
async def test_get_timezone_valid(mock_callback, mock_state, mock_db):
    mock_state.get_data = AsyncMock(return_value={"admin_id": 123, "bot_name": "Мама"})
    await get_timezone(mock_callback, mock_state, mock_db)
    mock_db.upsert_mama_config.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_choose_child_no_reply(mock_message, mock_state):
    mock_message.reply_to_message = None
    await choose_child(mock_message, mock_state)
    mock_message.answer.assert_called_once_with("Ответь (reply) на сообщение нужного человека.")


@pytest.mark.asyncio
async def test_get_child_name(mock_message, mock_state):
    mock_message.text = "Ребенок"
    await get_child_name(mock_message, mock_state)
    mock_state.update_data.assert_called()
    mock_message.answer.assert_called()


@pytest.mark.asyncio
async def test_set_gender_and_finish(mock_callback, mock_state, mock_db, mock_personality_manager):
    mock_state.get_data = AsyncMock(return_value={
        "admin_id": 123,
        "child_user_id": 456,
        "child_official_name": "Ребенок",
        "bot_name": "Мама",
        "config_id": 1
    })

    await set_gender_and_finish(mock_callback, mock_state, mock_db, mock_personality_manager)

    mock_db.add_participant.assert_called_once()
    mock_db.set_child.assert_called_once()
    mock_db.update_personality_prompt.assert_called_once()
    mock_callback.message.edit_text.assert_called_once()
import pytest
from core.prompt_factory import PromptFactory


# ---- Фикстуры

@pytest.fixture(scope="session")
def prompt_factory() -> PromptFactory:
    return PromptFactory()


@pytest.fixture(scope="session")
def test_config() -> dict:
    return {
        "id": 1,
        "bot_name": "Мамуля",
        "personality_prompt": "Ты немного саркастичная, но очень заботливая.",
        "child_participant_id": 10
    }


@pytest.fixture(scope="session")
def test_participants() -> list[dict]:
    return [
        {"id": 10, "user_id": 111, "custom_name": "Леша", "relationship_score": 75},
        {"id": 11, "user_id": 222, "custom_name": "Петя", "relationship_score": 50},
    ]


@pytest.fixture(scope="session")
def test_messages() -> list[dict]:
    return [
        {"user_id": 111, "text": "Мам, я сегодня поздно приду.", "participant_info": {"id": 10, "custom_name": "Леша"}},
        {"user_id": 333, "text": "Всем привет!", "participant_info": None},
    ]


# ---- Тесты

def test_create_session_start_prompt_full_data(prompt_factory, test_config, test_participants, test_messages):
    prompt = prompt_factory.create_session_start_prompt(
        config=test_config,
        participants=test_participants,
        messages=test_messages,
        time_of_day="morning",
        child_was_active=True
    )

    # базовая структура
    assert "persona" in prompt
    assert prompt["persona"]["name"] == test_config["bot_name"]
    assert prompt["persona"]["personality"] == test_config["personality_prompt"]

    # участники
    participants_state = prompt.get("current_state", {}).get("participants", {})
    assert participants_state[111]["name"] == "Леша"
    assert participants_state[111]["relationship_score"] == 75
    assert participants_state[111]["role"] == "child"
    assert participants_state[222]["name"] == "Петя"
    assert participants_state[222]["relationship_score"] == 50
    assert participants_state[222]["role"] == "member"

    # сообщения
    messages_state = prompt.get("input_data", {}).get("messages_to_analyze", [])
    assert any(msg["author_user_id"] == 111 and msg["text"] == "Мам, я сегодня поздно приду." for msg in messages_state)
    assert any(msg["author_user_id"] == 333 and msg["author_name"] == "New User" for msg in messages_state)

    # задача
    assert prompt.get("task", {}).get("action") == "START_CONVERSATION_WITH_BACKLOG_ANALYSIS"
    assert "morning" in prompt["task"]["details"]
    assert "Your child was active" in prompt["task"]["details"]


def test_create_online_prompt(prompt_factory, test_messages):
    prompt = prompt_factory.create_online_prompt(dialog_history=test_messages)
    assert "input_data" in prompt
    recent = prompt["input_data"]["recent_dialog_history"]
    assert any(msg["text"] == "Мам, я сегодня поздно приду." for msg in recent)
    assert prompt["task"]["action"] == "CONTINUE_LIVE_CONVERSATION"


def test_create_single_reply_prompt(prompt_factory, test_config, test_participants, test_messages):
    prompt = prompt_factory.create_single_reply_prompt(test_config, test_participants, test_messages[0])
    msg = prompt["input_data"]["message_to_reply"]
    assert msg["text"] == "Мам, я сегодня поздно приду."
    participants_state = prompt["current_state"]["participants"]
    assert participants_state[111]["role"] == "child"
    assert prompt["task"]["action"] == "SINGLE_DIRECT_REPLY"


def test_create_final_reply_prompt(prompt_factory, test_config, test_messages):
    prompt = prompt_factory.create_final_reply_prompt(test_config, test_messages)
    final_msgs = prompt["input_data"]["final_messages"]
    assert len(final_msgs) == 2
    assert prompt["task"]["action"] == "REPLY_AND_SAY_GOODBYE"


def test_create_goodbye_prompt(prompt_factory, test_config):
    prompt = prompt_factory.create_goodbye_prompt(test_config)
    assert "OutputFormat" not in prompt  # JSON больше не нужен
    assert prompt["task"]["action"] == "SAY_GOODBYE"
    assert "Write short warm goodbye message" in prompt["task"]["details"]

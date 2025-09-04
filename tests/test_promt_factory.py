import pytest
from core.prompt_factory import PromptFactory, Participant, Message


# ---- Фикстуры

@pytest.fixture(scope="session")
def prompt_factory() -> PromptFactory:
    """Простой инстанс нашего класса."""
    return PromptFactory()


@pytest.fixture(scope="session")
def test_config() -> dict:
    """Фикстура с полной конфигурацией 'Мамы'."""
    return {
        "id": 1,
        "bot_name": "Мамуля",
        "personality_prompt": "Ты немного саркастичная, но очень заботливая.",
        "child_participant_id": 10
    }


@pytest.fixture(scope="session")
def test_participants() -> list[Participant]:
    """Фикстура со списком известных участников."""
    return [
        {
            "id": 10,
            "user_id": 111,
            "custom_name": "Леша",
            "relationship_score": 75
        },
        {
            "id": 11,
            "user_id": 222,
            "custom_name": "Петя",
            "relationship_score": 50
        }
    ]


@pytest.fixture(scope="session")
def test_messages() -> list[Message]:
    """
    Фикстура со списком сообщений:
    - Одно от известного участника.
    - Одно от нового пользователя.
    """
    return [
        {
            "user_id": 111,
            "text": "Мам, я сегодня поздно приду.",
            "participant_info": {"id": 10, "custom_name": "Леша"}
        },
        {
            "user_id": 333,
            "text": "Всем привет!",
            "participant_info": None
        }
    ]


def test_create_gathering_prompt_full_data(
        prompt_factory: PromptFactory,
        test_config: dict,
        test_participants: list[Participant],
        test_messages: list[Message]
):
    prompt = prompt_factory.create_gathering_prompt(
        config=test_config,
        participants=test_participants,
        messages=test_messages,
        time_of_day="morning"
    )

    assert "ТВОЯ РОЛЬ" in prompt
    assert test_config['bot_name'] in prompt
    assert test_config['personality_prompt'] in prompt

    assert "УЧАСТНИКИ ДИАЛОГА" in prompt
    assert test_participants[0]['custom_name'] in prompt
    assert str(test_participants[0]['relationship_score']) in prompt
    assert "(твой ребенок)" in prompt

    assert "ИСТОРИЯ СООБЩЕНИЙ" in prompt
    assert test_messages[0]['text'] in prompt
    assert f"Новый пользователь (user_id: {test_messages[1]['user_id']})" in prompt

    assert "ТВОЯ ЗАДАЧА" in prompt
    assert "===JSON===" in prompt
    assert '"updates":' in prompt
    assert '"new_participants":' in prompt


@pytest.mark.parametrize(
    "time_of_day, expected_phrase",
    [
        ("morning", "доброго утра"),
        ("afternoon", "дневных обсуждениях"),
        ("evening", "хорошего вечера"),
        ("random", "внепланово проверить"),
    ]
)
def test_prompt_adapts_to_time_of_day(
        prompt_factory: PromptFactory, test_config: dict, time_of_day: str, expected_phrase: str
):
    prompt = prompt_factory.create_gathering_prompt(
        config=test_config,
        participants=[],
        messages=[],
        time_of_day=time_of_day
    )

    assert expected_phrase in prompt


def test_prompt_handles_empty_data(prompt_factory: PromptFactory, test_config: dict):
    prompt = prompt_factory.create_gathering_prompt(
        config=test_config,
        participants=[],
        messages=[],
        time_of_day="morning"
    )

    assert "Пока в чате нет никого, кого бы ты знала." in prompt
    assert "В чате за это время не было сообщений." in prompt
    assert "ТВОЯ РОЛЬ" in prompt
    assert "===JSON===" in prompt

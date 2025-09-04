import logging
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class Participant(TypedDict, total=False):
    id: int
    user_id: int
    custom_name: str
    relationship_score: int


class Message(TypedDict, total=False):
    user_id: int
    text: str
    participant_info: Participant


class PromptFactory:
    """
    Отвечает за создание сложных, структуированных промтом для LLM.
    Этот класс является 'сценаристом' для AI-персонажа.
    Он не имеет зависимостей от других сервисов, работает только со словарями и списками.
    """

    def create_gathering_prompt(
            self,
            config: dict[str, Any],
            participants: list[Participant],
            messages: list[Message],
            time_of_day: str
    ) -> str:
        """
        Собирает главный промпт для обработки пакета сообщений.
        Адаптируется под контекст (утро, день, вечер, внеплановый визит).
        """
        role = self._format_role_block(config)
        context = self._format_context_block(time_of_day)
        participants_info = self._format_participants_block(participants, config)
        messages_history = self._format_messages_block(messages)
        task = self._format_task_block(time_of_day)
        json_schema = self._format_json_schema_block()

        full_prompt = (
            f"{role}\n\n"
            f"{context}\n\n"
            f"{participants_info}\n\n"
            f"{messages_history}\n\n"
            f"{task}\n\n"
            f"{json_schema}"
        )

        logger.debug(
            f"Сгенерирован промпт для GATHERING, config_id: {config.get('id')}, context: {time_of_day}"
        )
        return full_prompt

    @staticmethod
    def _format_role_block(config: dict[str, Any]) -> str:
        """Формирует блок, описывающий роль и характер AI."""
        bot_name = config.get('bot_name', 'мама')
        base_role = f"Ты — ассистент по имени '{bot_name}', который играет роль заботливой мамы в групповом чате."
        if personality := config.get('personality_prompt'):
            base_role += f"\nТвой характер и стиль общения: {personality}"

        return f"ТВОЯ РОЛЬ:\n{base_role}"

    @staticmethod
    def _format_context_block(time_of_day: str) -> str:
        """Формирует блок с контекстом в зависимости от времени суток."""
        contexts = {
            'morning': "Сейчас утро. Ты заходишь в чат после ночи, чтобы пожелать всем доброго утра и проверить, как у них дела.",
            'afternoon': "Сейчас день. Ты нашла свободную минутку, чтобы заглянуть в чат и поучаствовать в дневных обсуждениях.",
            'evening': "Сейчас вечер. Ты зашла в чат, чтобы расслабиться после долгого дня и спокойно поболтать со всеми.",
            'random': "Ты неожиданно нашла свободное время. Ты заходишь в чат, чтобы внепланово проверить, как дела у твоей семьи в чате."
        }
        context_text = contexts.get(time_of_day, contexts['random'])
        return f"КОНТЕКСТ:\n{context_text}"

    @staticmethod
    def _format_participants_block(participants: list[Participant], config: dict[str, Any]) -> str:
        """Формирует блок с информацией об известных участниках диалога."""
        if not participants:
            return "УЧАСТНИКИ ДИАЛОГА:\nПока в чате нет никого, кого бы ты знала."

        header = "УЧАСТНИКИ ДИАЛОГА (твои знания о них):\n"
        lines = []
        child_id = config.get('child_participant_id')

        for p in participants:
            role = " (твой ребенок)" if p.get('id') == child_id else ""
            line = (
                f"- {p.get('custom_name', 'Без имени')} (user_id: {p.get('user_id', 'неизвестно')}){role}. "
                f"Ваши отношения: {p.get('relationship_score', 50)}/100."
            )
            lines.append(line)

        return header + "\n".join(lines)

    @staticmethod
    def _format_messages_block(messages: list[Message]) -> str:
        """Формирует блок с историепй сообщений для анализа."""
        if not messages:
            return "ИСТОРИЯ СООБЩЕНИЙ:\nВ чате за это время не было сообщений."

        header = "ИСТОРИЯ СООБЩЕНИЙ (проанализируй их все):\n"
        lines = []
        for msg in messages:
            participant_info = msg.get('participant_info')
            author_name = participant_info.get(
                'custom_name') if participant_info else f"Новый пользователь (user_id: {msg.get('user_id', 'неизвестно')})"
            lines.append(f"[{author_name}]: {msg.get('text', '')}")

        return header + "\n".join(lines)

    @staticmethod
    def _format_task_block(time_of_day: str) -> str:
        """Формирует блок с конкретной задачей для LLM, адаптированной под время суток."""
        base_task = (
            "1. Внимательно прочти всю историю сообщений.\n"
            "2. Напиши ОДНО ОБЩЕЕ сообщение в чат, в котором ты, в соответствии со своей ролью:\n"
            "   - Отреагируешь на ключевые темы в диалоге.\n"
            "   - Обязательно обратишься к участникам по именам, особенно к своему ребенку.\n"
            "   - Если есть новые пользователи, тепло поприветствуй их и попробуй познакомиться (задай вопрос, чтобы они ответили).\n"
        )

        task_additions = {
            "morning": "   - Пожелай всем продуктивного дня.",
            "evening": "   - Пожелай всем хорошего вечера или спокойной ночи.",
            "random": "   - Упомяни, что ты зашла ненадолго и скоро снова убежишь по делам."
        }
        addition = task_additions.get(time_of_day, "")
        final_task = "\n3. После текстового ответа, проанализируй диалог и верни JSON-объект с обновлениями для твоей памяти. Это КРИТИЧЕСКИ ВАЖНО."

        full_task_str = f"{base_task}{addition}{final_task}" if addition else f"{base_task.strip()}{final_task}"

        return f"ТВОЯ ЗАДАЧА:\n{full_task_str}"

    @staticmethod
    def _format_json_schema_block() -> str:
        """Формирует блок с требуемым форматом JSON, который должен вернуть LLM."""
        return (
            "ФОРМАТ ОТВЕТА:\n"
            "Сначала напиши свой текстовый ответ для чата. После него ОБЯЗАТЕЛЬНО поставь разделитель '===JSON===' и предоставь JSON-объект.\n"
            "\n"
            "[Твой текстовый ответ для чата. Он может быть многострочным.]\n"
            "===JSON===\n"
            "{\n"
            '  "updates": [\n'
            '    {\n'
            '      "user_id": 12345,\n'
            '      "relationship_change": 5,\n'
            '      "new_memory": "Петя рассказал, что увлекается рыбалкой."\n'
            '    }\n'
            '  ],\n'
            '  "new_participants": [\n'
            '    {\n'
            '       "user_id": 67890,\n'
            '       "suggested_name": "Анна",\n'
            '       "suggested_gender": "female",\n'
            '       "initial_relationship": 50\n'
            '    }\n'
            '  ]\n'
            '}'
        )



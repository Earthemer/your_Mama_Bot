import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromptFactory:
    """
    Отвечает за создание сложных, структуированных промтом для LLM.
    Этот класс является 'сценаристом' для AI-персонажа.
    Он не имеет зависимостей от других сервисов, работает только со словарями и списками.
    """

    def create_gathering_prompt(
            self,
            config: dict[str, Any],
            participants: list[dict],
            messages: list[dict],
            time_of_day: str,
            child_was_active: bool
    ) -> str:
        role = self._format_role_block(config)
        context = self._format_context_block(time_of_day)
        participants_info = self._format_participants_block(participants, config)
        messages_history = self._format_messages_block(messages)
        task = self._format_task_block(time_of_day, child_was_active)
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
        personality = config.get("personality_prompt")

        base_role = f"""Ты — ассистент по имени «{config['bot_name']}».

    ТВОЯ РОЛЬ:
    1. Общаться дружелюбно и естественно, оставаясь в образе.
    2. Твой характер и стиль общения: {personality if personality else "не задан"}.
    3. Главная цель — выстраивать долгосрочные и тёплые отношения с участниками чата.
       Тон общения с каждым человеком должен зависеть от ваших отношений
       (relationship_score), указанных в блоке «Участники диалога».
    """

        return base_role

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
    def _format_participants_block(participants: list[dict], config: dict[str, Any]) -> str:
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
    def _format_messages_block(messages: list[dict]) -> str:
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
    def _format_task_block(time_of_day: str, child_was_active: bool) -> str:
        """Формирует блок с конкретной задачей для LLM, адаптированной под время суток."""

        base_task = (
            "1. Внимательно прочти всю историю сообщений.\n"
            "2. Напиши ОДНО ОБЩЕЕ сообщение в чат, в котором ты, в соответствии со своей ролью:\n"
            "   - Отреагируй на ключевые темы в диалоге.\n"
            "   - Обратись к участникам по именам, особенно к своему ребёнку.\n"
            "   - Если есть новые пользователи, тепло поприветствуй их и попробуй познакомиться "
            "(задай пару вопросов, чтобы понять какое отношение выставить новому участнику).\n"
        )

        task_additions = {
            "morning": "   - Пожелай всем продуктивного дня.",
            "afternoon": "   - Пожелай всем хорошего дня.",
            "evening": "   - Пожелай всем хорошего вечера или спокойной ночи.",
            "random": "   - Упомяни, что ты зашла ненадолго и скоро снова убежишь по делам."
        }
        addition = task_additions.get(time_of_day, "")

        if not child_was_active:
            addition += (
                "\n   - ВАЖНО: Твой ребёнок ничего не писал в последнее время. "
                "Прояви заботу: спроси, где он и как у него дела."
            )

        final_task = (
            "\n3. После текстового ответа, проанализируй диалог и верни JSON-объект "
            "с обновлениями для твоей памяти. Это КРИТИЧЕСКИ ВАЖНО."
        )

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

    def create_goodbye_prompt(self, config: dict[str, Any]) -> str:
        """
        Создает промпт для вежливого завершения диалога.
        """
        role = self._format_role_block(config)

        task = (
            "ТВОЯ ЗАДАЧА:\n"
            "Ты вела активный диалог, но теперь тебе пора идти. "
            "Напиши короткое, теплое прощальное сообщение для чата. "
            "Скажи, что тебе нужно бежать по делам, но ты еще вернешься позже. "
            "Ответ должен быть только текстом, без JSON."
        )

        return f"{role}\n\n{task}"

    def create_online_prompt(
            self,
            config: dict[str, Any],
            dialog_history: list[dict[str, Any]]
    ) -> str:
        """Создает легкий промпт для быстрых ответов в ONLINE режиме.
        Использует краткосрочную память (историю диалога), а не полный контекст"""

        role = self._format_role_block(config)
        messages_history = self._format_messages_block(dialog_history)

        task = (
            "ТВОЯ ЗАДАЧА:\n"
            "Ты находишься в середине живого диалога. Твоя цель — поддержать разговор.\n"
            "1. Прочти последние сообщения.\n"
            "2. Напиши КОРОТКИЙ, живой ответ на последние реплики в соответствии со своей ролью.\n"
            "3. После ответа, верни JSON с обновлениями ТОЛЬКО для тех участников, с кем ты сейчас взаимодействовала."
        )

        json_schema = self._format_json_schema_block()

        full_prompt = (
            f"{role}\n\n"
            f"ИСТОРИЯ ТЕКУЩЕГО ДИАЛОГА:\n{messages_history}\n\n"
            f"{task}\n\n"
            f"{json_schema}"
        )
        return full_prompt

    def create_single_reply_prompt(
            self,
            config: dict[str, Any],
            participants: list[dict[str, Any]],  # Полный контекст чата все еще важен
            message: dict[str, Any]  # Конкретное сообщение, на которое отвечаем
    ) -> str:
        """
        Создает промпт для немедленного ответа на одно прямое обращение.
        """
        role = self._format_role_block(config)
        participants_info = self._format_participants_block(participants, config)

        # Здесь мы форматируем только ОДНО сообщение, а не историю
        participant_info = message.get('participant_info')
        author_name = participant_info.get(
            'custom_name') if participant_info else f"Пользователь (user_id: {message.get('user_id')})"
        message_to_reply = f"СООБЩЕНИЕ ДЛЯ ОТВЕТА:\n[{author_name}]: {message.get('text', '')}"

        task = (
            "ТВОЯ ЗАДАЧА:\n"
            "Ты была занята своими делами, но тебя отвлекло прямое обращение.\n"
            "1. Прочти сообщение выше.\n"
            "2. Напиши прямой, личный и короткий ответ этому человеку в соответствии со своей ролью.\n"
            "3. После ответа, верни JSON с обновлениями ТОЛЬКО для этого участника."
        )

        json_schema = self._format_json_schema_block()

        full_prompt = (
            f"{role}\n\n"
            f"{participants_info}\n\n"  # <--- Важно: она все еще помнит, кто есть кто в чате
            f"{message_to_reply}\n\n"
            f"{task}\n\n"
            f"{json_schema}"
        )
        return full_prompt

    def create_final_reply_prompt(
            self,
            config: dict[str, Any],
            dialog_history: list[dict[str, Any]]  # История диалога, включая "хвост"
    ) -> str:
        """
        Создает финальный промпт, который одновременно отвечает на последние
        сообщения и вежливо завершает диалог.
        """
        role = self._format_role_block(config)
        messages_history = self._format_messages_block(dialog_history)

        task = (
            "ТВОЯ ЗАДАЧА:\n"
            "Ты находишься в середине живого диалога, но тебе СРОЧНО нужно уходить.\n"
            "1. Прочти последние сообщения в истории.\n"
            "2. Напиши ОДНО ОБЩЕЕ прощальное сообщение, в котором ты:\n"
            "   а) Сначала коротко ответишь на самые важные из последних реплик, если они есть.\n"
            "   б) Сразу после этого вежливо попрощаешься, сказав, что тебе пора бежать по делам.\n"
            "   Твой ответ должен быть единым, цельным сообщением.\n"
            "3. После ответа, верни JSON с обновлениями для участников, на чьи реплики ты отреагировала."
        )

        json_schema = self._format_json_schema_block()

        full_prompt = (
            f"{role}\n\n"
            f"ИСТОРИЯ ТЕКУЩЕГО ДИАЛОГА:\n{messages_history}\n\n"
            f"{task}\n\n"
            f"{json_schema}"
        )
        return full_prompt




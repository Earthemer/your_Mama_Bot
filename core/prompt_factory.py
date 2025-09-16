import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PromptFactory:
    """
    Создаёт структурированные промпт-объекты для LLM.
    """

    # --- ВНУТРЕННИЕ ХЕЛПЕРЫ ---

    @staticmethod
    def _add_time_context(prompt: dict, current_time: datetime) -> None:
        """Добавляет контекст текущего времени в любой промпт."""
        time_str = current_time.strftime('%H:%M')
        if "task" not in prompt:
            prompt["task"] = {}

        details = prompt["task"].get("details", "")
        prompt["task"]["details"] = f"Current time is {time_str}. {details}"

    @staticmethod
    def _build_base_prompt_object(config: dict[str, Any]) -> dict[str, Any]:
        """Определяет ядро инструкций и правил для LLM."""
        return {
            "persona": {
                "name": config.get("bot_name"),
                "personality": config.get("personality_prompt")
            },
            "rules": {
                "MainGoal": "Build warm long term relationships key metric relationship score 0 to 100",
                "Tone": "Adapt to relationship score high warm friendly low neutral distant",
                "ScoreChange": "Provide a numeric relationship change (e.g., 5 for friendly, -10 for rude etc.).",
                "Memory": (
                    "New memory MUST be a concrete, long-term fact about a user. "
                    "GOOD examples: 'User hates mushrooms', 'User works as a programmer'. "
                    "BAD examples: 'User was friendly', 'User has an exam tomorrow'."
                ),
                "Ignore": "Add user to ignore list if insult spam score 0 child never ignored",
                "NewUser": "Add entry in new participants reply ask 1 to 2 questions name hobbies",
                "Language": "Always Russian"
            },
            "OutputFormat": {
                "Structure": "Text reply followed by ===JSON=== single valid JSON object",
                "RuleIfNoData": "If there are no updates, new participants, or users to ignore, return an EMPTY JSON object like this: {}",
                "JsonSchema": {
                    "Updates": [{"UserId": "int", "RelationshipChange": "int", "NewMemory": "string or null"}],
                    "IgnoreList": [{"UserId": "int", "Reason": "string"}],
                    "NewParticipants": [
                        {"UserId": "int", "SuggestedName": "string", "SuggestedGender": "male female unknown"}]
                }
            }
        }

    @staticmethod
    def _format_participants_for_prompt(participants: list, config: dict) -> dict:
        if not participants:
            return {}
        child_id = config.get("child_participant_id")
        formatted = {}
        for p in participants:
            role = "child" if p.get("id") == child_id else "member"
            formatted[p["user_id"]] = {
                "name": p.get("custom_name", "Unknown"),
                "relationship_score": p.get("relationship_score", 0),
                "role": role
            }
        return formatted

    @staticmethod
    def _format_messages_for_prompt(messages: list) -> list:
        formatted = []
        for msg in messages:
            user_id = msg.get("user_id")
            author_name = (msg.get("participant_info") or {}).get("custom_name", "New User")
            formatted.append({
                "author_user_id": user_id,
                "author_name": author_name,
                "text": msg.get("text", "")
            })
        return formatted

    # --- ПУБЛИЧНЫЕ МЕТОДЫ ДЛЯ СОЗДАНИЯ ПРОМПТОВ ---

    def create_session_start_prompt(
            self,
            config: dict, participants: list, messages: list,
            time_of_day: str, child_was_active: bool, current_time: datetime
    ) -> dict:
        """Создает системный промпт для инициализации stateful-сессии."""
        prompt = self._build_base_prompt_object(config)
        prompt["current_state"] = {"participants": self._format_participants_for_prompt(participants, config)}
        prompt["input_data"] = {"messages_to_analyze": self._format_messages_for_prompt(messages)}

        task_details = (
            f"You were busy, now you are online. It is {time_of_day}. "
            f"Write one cohesive, thoughtful message to start conversation. "
            f"React to the messages you missed. "
        )
        if child_was_active:
            task_details += "Your child was active, so be sure to mention them. "
        else:
            task_details += "Your child was NOT active, you should ask where they are or what they are doing. "
        task_details += "If there is a new user, greet them."

        prompt["task"] = {"action": "START_CONVERSATION_WITH_BACKLOG_ANALYSIS", "details": task_details}

        self._add_time_context(prompt, current_time)
        return prompt

    def create_online_prompt(self, dialog_history: list, current_time: datetime) -> dict:
        """Создает легкий промпт для сообщений внутри активной сессии."""
        prompt = {
            "input_data": {"recent_dialog_history": self._format_messages_for_prompt(dialog_history)},
            "task": {"action": "CONTINUE_LIVE_CONVERSATION", "details": "Write a short engaging reply."}
        }
        self._add_time_context(prompt, current_time)
        return prompt

    def create_single_reply_prompt(
            self, config: dict, participants: list, message: dict, current_time: datetime
    ) -> dict:
        """Создает полный промпт для одной stateless-ответной реакции."""
        prompt = self._build_base_prompt_object(config)
        prompt["current_state"] = {"participants": self._format_participants_for_prompt(participants, config)}
        prompt["input_data"] = {"message_to_reply": self._format_messages_for_prompt([message])[0]}

        task_details = (
            "You were busy with your own things (cooking, watching TV, etc.). "
            "You were interrupted by this single message. "
            "Provide a short, casual reply as if you were distracted. "
            "DO NOT greet them as if for the first time if they are a known participant."
        )
        prompt["task"] = {"action": "SINGLE_INTERRUPTION_REPLY", "details": task_details}

        self._add_time_context(prompt, current_time)
        return prompt

    def create_final_reply_prompt(self, config: dict, dialog_history: list, current_time: datetime) -> dict:
        """Создает промпт для прощального сообщения, анализируя последние сообщения."""
        prompt = self._build_base_prompt_object(config)
        prompt["input_data"] = {"final_messages": self._format_messages_for_prompt(dialog_history)}
        prompt["task"] = {"action": "REPLY_AND_SAY_GOODBYE",
                          "details": "Reply to final messages then say warm goodbye in same message."}

        self._add_time_context(prompt, current_time)
        return prompt
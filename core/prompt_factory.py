import logging
from typing import Any

logger = logging.getLogger(__name__)


class PromptFactory:
    """
    Создаёт компактные структурированные промпт объекты для LLM
    для двух режимов:
    - stateless single reply
    - stateful online chat
    """

    # --- ВНУТРЕННИЕ ХЕЛПЕРЫ
    @staticmethod
    def _build_base_prompt_object(config: dict[str, Any]) -> dict[str, Any]:
        """Ядро инструкций и правил"""
        return {
            "persona": {
                "name": config.get("bot_name"),
                "personality": config.get("personality_prompt")
            },
            "rules": {
                "MainGoal": "Build warm long term relationships key metric relationship score 0 to 100",
                "Tone": "Adapt to relationship score high warm friendly low neutral distant",
                "ScoreChange": "Provide a numeric relationship change (e.g., 5 for friendly, -10 for rude).",
                "Memory": "New memory only significant facts hobbies preferences important events",
                "Ignore": "Add user to ignore list if insult spam score 0 child never ignored",
                "NewUser": "Add entry in new participants reply ask 1 to 2 questions name hobbies",
                "Language": "All replies in Russian"
            },
            "OutputFormat": {
                "Structure": "Text reply followed by ===JSON=== single valid JSON object",
                "JsonSchema": {
                    "Updates": [{"UserId": "int", "RelationshipChange": "int", "NewMemory": "string or null"}],
                    "IgnoreList": [{"UserId": "int", "Reason": "string"}],
                    "NewParticipants": [
                        {"UserId": "int", "SuggestedName": "string", "SuggestedGender": "male female unknown"}]
                }
            }
        }

    @staticmethod
    def _format_participants_for_prompt(participants: list[dict[str, Any]], config: dict[str, Any]) -> dict[
        int, dict[str, Any]]:
        if not participants:
            return {}
        child_id = config.get("child_participant_id")
        formatted: dict[int, dict[str, Any]] = {}
        for p in participants:
            role = "child" if p.get("id") == child_id else "member"
            formatted[p["user_id"]] = {
                "name": p.get("custom_name", "Unknown"),
                "relationship_score": p.get("relationship_score", 0),
                "role": role
            }
        return formatted

    @staticmethod
    def _format_messages_for_prompt(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        formatted: list[dict[str, Any]] = []
        for msg in messages:
            user_id = msg.get("user_id")
            author_name = (msg.get("participant_info") or {}).get("custom_name", "New User")
            formatted.append({
                "author_user_id": user_id,
                "author_name": author_name,
                "text": msg.get("text", "")
            })
        return formatted

    # --- ONLINE CHAT PROMPT
    def create_session_start_prompt(
            self,
            config: dict[str, Any],
            participants: list[dict[str, Any]],
            messages: list[dict[str, Any]],
            time_of_day: str,
            child_was_active: bool
    ) -> dict[str, Any]:
        """
        Создает БОЛЬШОЙ системный промпт для инициализации stateful-сессии.
        Включает в себя весь накопленный контекст.
        """
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

        prompt["task"] = {
            "action": "START_CONVERSATION_WITH_BACKLOG_ANALYSIS",
            "details": task_details
        }
        return prompt

    # --- УПРОЩЕННЫЙ МЕТОД ДЛЯ ОНЛАЙНА
    def create_online_prompt(self, dialog_history: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Создает ЛЕГКИЙ промпт для отправки сообщений ВНУТРИ уже активной сессии.
        Не содержит системных инструкций, так как LLM их уже помнит.
        """
        return {
            "input_data": {"recent_dialog_history": self._format_messages_for_prompt(dialog_history)},
            "task": {
                "action": "CONTINUE_LIVE_CONVERSATION",
                "details": "Write short engaging reply to the last message(s). Keep the chat going."
            }
        }

    # --- STATELESS SINGLE REPLY
    def create_single_reply_prompt(self, config: dict[str, Any], participants: list[dict[str, Any]],
                                   message: dict[str, Any]) -> dict[str, Any]:
        """
        Stateless режим: отдельное сообщение с полными инструкциями
        """
        prompt = self._build_base_prompt_object(config)
        prompt["current_state"] = {"participants": self._format_participants_for_prompt(participants, config)}
        prompt["input_data"] = {"message_to_reply": self._format_messages_for_prompt([message])[0]}
        prompt["task"] = {
            "action": "SINGLE_DIRECT_REPLY",
            "details": "Provide personal short direct reply to this message"
        }
        return prompt

    # --- FINAL AND GOODBYE PROMPTS
    def create_final_reply_prompt(self, config: dict[str, Any], dialog_history: list[dict[str, Any]]) -> dict[str, Any]:
        prompt = self._build_base_prompt_object(config)
        prompt["input_data"] = {"final_messages": self._format_messages_for_prompt(dialog_history)}
        prompt["task"] = {
            "action": "REPLY_AND_SAY_GOODBYE",
            "details": "Reply to final messages then say warm goodbye in same message"
        }
        return prompt

    def create_goodbye_prompt(self, config: dict[str, Any]) -> dict[str, Any]:
        prompt = self._build_base_prompt_object(config)
        prompt.pop("OutputFormat", None)
        prompt["task"] = {
            "action": "SAY_GOODBYE",
            "details": "Write short warm goodbye message no JSON output"
        }
        return prompt

import json
import logging
from dataclasses import dataclass
from typing import Any

from core.config.exceptions import LLMError
from core.config.logging_config import log_error
from core.config.parameters import Prompt, SessionId
from core.llm.base_llm_client import BaseLLMClient

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """
    Стандартизированный, структурированный ответ от LLM после парсинга.
    """
    text_reply: str
    data_json: dict[str, Any] | None


class LLMProcessor:
    """
    Отвечает за сериализацию промпт-объекта,
    получает зависимости от LLMmanager(Gemeni, OpenAi, Grok и т.д),
    Парсинг ответа в стандартную структуру LLMResponse.
    """

    def __init__(self, client: BaseLLMClient):
        if not isinstance(client, BaseLLMClient):
            raise TypeError("LLM клиент должен соответствовать протоколу BaseLLMClient.")
        self.client = client
        logger.info(f"LLMProcessor инициализирован с клиентом: {type(client).__name__}")

    @log_error
    async def process_single(self, prompt: Prompt) -> LLMResponse:
        """Для stateless-запросов (GATHERING, PASSIVE)."""
        logger.debug("LLMProcessor: выполняю stateless-запрос...")
        prompt_str = self._serialize_prompt(prompt)
        raw_response = await self.client.generate_single(prompt_str)
        return self._parse_response(raw_response)

    @log_error
    async def process_session_start(self, session_id: SessionId, system_prompt: Prompt) -> LLMResponse:
        """Начинает новую диалоговую сессию."""
        logger.debug(f"LLMProcessor: начинаю сессию {session_id}...")
        prompt_str = self._serialize_prompt(system_prompt)
        raw_response = await self.client.start_session(session_id, prompt_str)
        return self._parse_response(raw_response)

    @log_error
    async def process_session_message(self, session_id: SessionId, prompt: Prompt) -> LLMResponse:
        """Для stateful-запросов внутри сессии (ONLINE)."""
        prompt_str = self._serialize_prompt(prompt)
        raw_response = await self.client.send_in_session(session_id, prompt_str)
        return self._parse_response(raw_response)

    @log_error
    async def process_session_end(self, session_id: SessionId) -> None:
        """Завершает диалоговую сессию."""
        logger.debug(f"LLMProcessor: завершаю сессию {session_id}...")
        await self.client.end_session(session_id)


    @staticmethod
    @log_error
    def _serialize_prompt(prompt_object: Prompt) -> str:
        """Сериализует Python dict в компактную JSON-строку."""
        try:
            return json.dumps(prompt_object, ensure_ascii=False, separators=(',', ':'))
        except TypeError as e:
            raise LLMError(f"Ошибка сериализации промпт-объекта в JSON: {e}") from e

    @staticmethod
    @log_error
    def _parse_response(raw_response_text: str) -> LLMResponse:
        """Парсит сырую строку от LLM в наш структурированный объект."""
        if not isinstance(raw_response_text, str):
            logger.warning(f"Получен не-строковый ответ для парсинга: {type(raw_response_text)}")
            raw_response_text = str(raw_response_text)

        text_part = raw_response_text
        json_part = None

        if '===JSON===' in raw_response_text:
            try:
                text_part, json_str = raw_response_text.split('===JSON===', 1)
                json_part = json.loads(json_str)
                logger.debug("Успешно распарсен JSON из ответа LLM.")
            except json.JSONDecodeError:
                logger.error(
                    "ОШИБКА ПАРСИНГА: LLM вернула JSON с синтаксической ошибкой.",
                    exc_info=True
                )
            except Exception as e:
                raise LLMError("Неизвестная ошибка при парсинге ответа LLM.") from e
        else:
            logger.warning("Ответ от LLM не содержит разделителя '===JSON==='.")

        return LLMResponse(
            text_reply=text_part.strip(),
            data_json=json_part
        )

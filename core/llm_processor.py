import json
import logging

from core.logging_config import log_error
from dataclasses import dataclass
from typing import Any

from core.llm_manager import LLMManager
from core.llm_manager import LLMError

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Стандартизированный, структурированный ответ от LLM после парсинга.
    'Контракт', который процессор предоставляет остальной системе."""
    text_reply: str
    data_json: dict[str, Any] | None


class LLMProcessor:
    """Отвечает за общение с LLM через LLMManager и за парсинг ответа в стандартную структуру LLMResponse.`"""

    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager
        logger.info("LLMProcessor инициализирован.")

    @log_error
    async def execute_and_parse(self, prompt: str) -> LLMResponse:
        """
        Главный метод. Выполняет промпт и разбирает ответ.

        1. Получает сырой текст от LLMManager.
        2. Ищет разделитель '===JSON==='.
        3. Пытается распарсить JSON.
        4. В случае любой ошибки парсинга, возвращает JSON как None,
           но всегда возвращает текстовую часть.
        """
        try:
            raw_response = await self.llm_manager.get_raw_response(prompt)
        except LLMError as e:
            raise LLMError(f"LLMManager не смог получить ответ от API: {e}") from e

        text_part = raw_response
        json_part = None

        if '===JSON===' in raw_response:
            try:
                text_part, json_str = raw_response.split('===JSON===', 1)
                json_part = json.loads(json_str)
                logger.debug("Успешно распарсен JSON из ответа LLM.")
            except json.JSONDecodeError:
                logger.error(
                    "ОШИБКА ПАРСИНГА: LLM вернула JSON с синтаксической ошибкой.",
                    exc_info=True
                )
            except Exception as e:
                raise LLMError("Неизвестная ошибка при парсинге ответа LLM.")
        else:
            logger.warning("Ответ от LLM не содержит разделителя '===JSON==='.")

        return LLMResponse(
            text_reply=text_part.strip(),
            data_json=json_part
        )



import logging

from asyncio import to_thread
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from core.llm.base_llm_client import BaseLLMClient
from core.config.exceptions import LLMError
from core.config.parameters import SessionId, Prompt, GENERATION_CONFIG, SAFETY_SETTINGS
from core.config.logging_config import log_error

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """Реализация LLM-клиента для Google Gemini API."""

    @log_error
    def __init__(self, api_key: str):
        if not api_key:
            raise LLMError("API-ключ для Gemini не предоставлен!")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
        self._session: dict[SessionId, genai.ChatSession] = {}
        logger.info("GeminiClient инициализирован.")

    @log_error
    async def generate_single(self, prompt: Prompt) -> str:
        """Сингл (stateless) генерация для PASSIVE режима."""
        logger.debug("GeminiClient: выполняю stateless-запрос...")
        try:
            response = await to_thread(
                self.model.generate_content,
                contents=prompt,
                generation_config=GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS
            )
            return response.text
        except (google_exceptions.GoogleAPICallError, ValueError) as e:
            raise LLMError(f"Ошибка API Gemini при stateless-запросе: {e}") from e
        except Exception as e:
            raise LLMError(f"Непредвиденная ошибка в GeminiClient.generate_single: {e}") from e

    @log_error
    async def start_session(self, session_id: SessionId, system_prompt: Prompt) -> str:
        """Инициализирует stateful-сессию (чат) и возвращает первый ответ."""
        logger.debug(f"GeminiClient: стартую сессию {session_id}...")
        if session_id in self._session:
            logger.warning(f"Сессия {session_id} уже существует. Перезапускаю.")
            del self._session[session_id]

        try:
            chat_session = self.model.start_chat()
            response = await to_thread(
                chat_session.send_message,
                content=system_prompt,
                generation_config=GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS
            )
            self._session[session_id] = chat_session
            logger.debug(f"Сессия {session_id} успешно создана.")
            return response.text
        except (google_exceptions.GoogleAPICallError, ValueError) as e:
            raise LLMError(f"Ошибка API Gemini при старте сессии {session_id}: {e}") from e
        except Exception as e:
            raise LLMError(f"Непредвиденная ошибка в GeminiClient.start_session: {e}") from e

    @log_error
    async def send_in_session(self, session_id: SessionId, prompt: str) -> str:
        """Отправляет сообщение в существующую сессию."""
        logger.debug(f"GeminiClient: отправляю сообщение в сессию {session_id}...")
        if session_id not in self._session:
            raise LLMError(f"Попытка отправить сообщение в несуществующую сессию: {session_id}")

        try:
            chat_session = self._session[session_id]
            response = await to_thread(
                chat_session.send_message,
                content=prompt,
                generation_config=GENERATION_CONFIG,
                safety_settings=SAFETY_SETTINGS
            )
            return response.text
        except (google_exceptions.GoogleAPICallError, ValueError) as e:
            raise LLMError(f"Ошибка API Gemini в сессии {session_id}: {e}") from e
        except Exception as e:
            raise LLMError(f"Непредвиденная ошибка в GeminiClient.send_in_session: {e}") from e

    @log_error
    async def end_session(self, session_id: SessionId) -> None:
        """
        Завершает/удаляет сессию. Операция идемпотентна.
        """
        logger.debug(f"GeminiClient: завершаю сессию {session_id}...")
        if session_id in self._session:
            del self._session[session_id]
            logger.info(f"Сессия {session_id} удалена из памяти клиента.")
        else:
            logger.warning(f"Попытка завершить несуществующую сессию {session_id}.")

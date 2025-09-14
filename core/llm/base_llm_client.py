from typing import runtime_checkable, Protocol

from core.config.parameters import Prompt, SessionId

@runtime_checkable
class BaseLLMClient(Protocol):
    """
    Контракт для любых LLM-клиентов.

    Правила:
    - Все методы асинхронные = внешний код ожидает awaitable API;
    - generate_single/send_in_session возвращают "сырое" текстовое тело ответа (str);
    - при ошибке клиент должен бросать LLMError;
    - start_session создаёт контекст/сессию, end_session его удаляет идемпотентно;
    - session_id (SessionId) — произвольный идентификатор, удобный для вызывающей стороны
    """
    async def generate_single(self, prompt: Prompt) -> str:
        """Сингл (stateless) генерация."""
        pass

    async def start_session(self, session_id: SessionId, system_prompt: Prompt) -> str:
        """
        Инициализация stateful-сессию (чат).

        После выполнения методы должно быть возможно вызывать send_in_session с тем же session_id.
        Реализация сама хранит объекты сессий.
        """
        pass

    async def send_in_session(self, session_id: SessionId, prompt: Prompt) -> str:
        """Отправить сообщение в существующую сессию и получить ответ."""
        pass

    async def end_session(self, session_id: SessionId) -> None:
        """
        Завершить/удалить сессию. Операция должна быть идемпотентной.

        После вызова дальнейшие send_in_session для этого session_id должны
        либо создавать новую сессию (при необходимости), либо бросать ошибку —
        это решается реализацией.
        """


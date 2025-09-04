import logging
from core.logging_config import log_error
from asyncio import to_thread
from google import genai
from google.genai import types
from core.exceptions import LLMError

logger = logging.getLogger(__name__)

GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.9,
    top_p=1,
    top_k=1,
    max_output_tokens=2048,
    safety_settings=[
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
    ]
)

class LLMManager:
    """
    Управляет взаимодействием с LLM.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API ключ не предоставлен!")

        self._client = genai.Client(api_key=api_key)
        logger.debug("LLManager инициализирован.")

    @log_error
    async def get_raw_response(self, prompt: str) -> str:
        """Отправляет промт в LLM и возрващает текстовый ответ. """
        try:
            response = await to_thread(
                self._client.models.generate_content,
                model='gemini-1.5-flash',
                contents=prompt,
                config=GENERATION_CONFIG
            )

            if not response.text:
                raise LLMError("Модель не вернула текстовый ответ.")
            return response.text

        except Exception as e:
            raise LLMError("Не удалось получить ответ от нейросети.")
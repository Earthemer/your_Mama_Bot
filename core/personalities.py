import logging
import json
import random

from pathlib import Path
from typing import Any
from core.config.exceptions import UnexpectedError
from core.config.logging_config import log_error

logger = logging.getLogger(__name__)

class PersonalityManager:
    """Отвечает за загрузку и предоставление случайного характера для бота."""
    def __init__(self, file_path: Path = None):
        if file_path is None:
            self.file_path = Path(__file__).parent / 'config' / 'personalities.json'
        else:
            self.file_path = file_path

        self._personalities: list[dict[str, Any]] = self._load_personalities()

    @log_error
    def _load_personalities(self) -> list[dict[str, Any]]:
        """Загружает характеры из JSON-файла."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                personalities = json.load(f)
                logger.debug(f"Успешно загружено {len(personalities)} характеров.")
                return personalities
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise UnexpectedError(f"FATAL: Could not load personalities.json from {self.file_path}: {e}")

    def get_random_personality(self) -> dict[str, Any]:
        """Возвращает случайный характер из загруженного списка."""
        if not self._personalities:
            raise UnexpectedError(f"FATAL: Could not load personalities.json from {self.file_path}.")
        return random.choice(self._personalities)






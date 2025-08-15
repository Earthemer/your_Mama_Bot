import logging

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from core.database import AsyncDatabaseManager
from core.llm_service import LLMManager, LLMError
from core.config.parameters import ACTIVE_MODE_DURATION_MINUTES, CREATIVE_RESPONSES_LIMIT


logger = logging.getLogger(__name__)







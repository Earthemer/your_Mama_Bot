import os
import logging
from core.config.logging_config import log_error

logger = logging.getLogger(__name__)

@log_error
def get_int_env(var_name: str, default: int) -> int:
    """Читает переменную окружения как целое число."""
    value_str = os.getenv(var_name, str(default))
    try:
        value = int(value_str)
        if value < 0 and "PORT" not in var_name.upper():
            logger.warning(f"Значение {var_name} ('{value_str}') должно быть положительным. Используется default: {default}.")
            return default
        return value
    except (ValueError, TypeError):
        logger.warning(f"Некорректное значение {var_name} в .env ('{value_str}'). Используется default: {default}.")
        return default

@log_error
def get_float_env(var_name: str, default: float) -> float:
    """Читает переменную окружения как float."""
    value_str = os.getenv(var_name, str(default))
    try:
        value = float(value_str)
        if value <= 0:
            logger.warning(f"{var_name} ('{value_str}') должно быть положительным. Используется default: {default}.")
            return default
        return value
    except (ValueError, TypeError):
        logger.warning(f"Некорректное значение {var_name} ('{value_str}'). Используется default: {default}.")
        return default

@log_error
def get_str_env(var_name: str, default: str) -> str:
    """Читает переменную окружения как строку."""
    return os.getenv(var_name, default)
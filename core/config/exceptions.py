class CustomError(Exception):
    """Базовая ошибка базы данных."""
    pass


class DatabaseConnectionError(CustomError):
    """Ошибка соединения с базой данных."""
    pass


class DatabaseQueryError(CustomError):
    """Ошибка выполнения запроса (неуникальные, невалидные, синтаксические и пр.)."""
    pass


class DuplicateUserError(CustomError):
    """Пользователь с таким именем уже существует (уникальность нарушена)."""
    pass


class EntryNotFoundError(CustomError):
    """Запись в базе не найдена (общая ошибка поиска записей)."""
    pass


class UserNotFoundError(CustomError):
    """Пользователь не найден (частный случай EntryNotFound)."""
    pass


class UserCreationError(CustomError):
    """Пользователь не был создан должным образом."""
    pass


class PoolConnectionError(CustomError):
    """Ошибка соединения с пулом подключения."""
    pass


class LLMError(CustomError):
    """Ошибка при работе с LLM."""
    pass


class AiogramError(CustomError):
    """Ошибка при работе с aiogram."""
    pass


class SchedulerError(CustomError):
    """Ошибка при работе с AsyncIOScheduler."""
    pass


class RedisConnectionError(CustomError):
    """Ошибка при работе с Redis db."""
    pass


class BrainServiceError(CustomError):
    """Ошибка при работе с brain_service."""
    pass


class ListenerError(CustomError):
    """Ошибка при работе хендлера listener. """
    pass


class UnexpectedError(CustomError):
    """Непредвидимая ошибка."""
    pass

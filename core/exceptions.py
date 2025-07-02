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

class UnexpectedError(CustomError):
    """Непредвидимая ошибка"""
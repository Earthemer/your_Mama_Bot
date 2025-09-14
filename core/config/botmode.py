from enum import Enum

class BotMode(str, Enum):
    """Режимы работы бота."""
    GATHERING = 'GATHERING'
    ONLINE = 'ONLINE'
    PASSIVE = 'PASSIVE'
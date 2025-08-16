import logging

from dotenv import load_dotenv
from faker import Faker

from core.utils import get_str_env, get_int_env, get_float_env


logger = logging.getLogger(__name__)
load_dotenv()

# ------- TOKENS -------
BOT_TOKEN = get_str_env('BOT_TOKEN', 'default')
if BOT_TOKEN == 'default':
    logger.critical("Токен бота (BOT_TOKEN) не найден в .env файле!")
    exit("Токен бота не найден!")

GEMINI_API_KEY = get_str_env('GEMINI_API_KEY', 'default')
if GEMINI_API_KEY == 'default':
    logger.critical("API ключ для Gemini (GEMINI_API_KEY) не найден в .env файле!")
    exit("API ключ для Gemini не найден!")

# ------- DSN -------
DB_USER = get_str_env('DB_USER', 'postgres')
DB_PASSWORD = get_str_env('DB_PASSWORD', 'password')
DB_HOST = get_str_env('DB_HOST', 'localhost')
DB_PORT = get_int_env('DB_PORT', 5432)
DB_NAME = get_str_env('DB_NAME', 'your_mama_bot_db')
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ------- DSN for test_db -------
TEST_DB_USER = get_str_env('TEST_DB_USER', 'postgres')
TEST_DB_PASSWORD = get_str_env('TEST_DB_PASSWORD', 'password')
TEST_DB_HOST = get_str_env('TEST_DB_HOST', 'localhost')
TEST_DB_PORT = get_int_env('TEST_DB_PORT', 5432)
TEST_DB_NAME = get_str_env('TEST_DB_NAME', 'test_mama_db')
TEST_DATABASE_URL = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"

TEST_TABLES = [
    "daily_events",
    "long_term_memory",
    "participants",
    "mama_configs",
]


# ------- FOR POOL -------
POOL_PARAMETERS = {
    'POOL_MIN_SIZE': get_int_env('POOL_MIN_SIZE', 1),
    'POOL_MAX_SIZE': get_int_env('POOL_MAX_SIZE', 10),
    'DEFAULT_COMMAND_TIMEOUT_SECONDS': get_float_env('DEFAULT_COMMAND_TIMEOUT_SECONDS', 5.0),
    'CONNECT_RETRY_ATTEMPTS': get_int_env('CONNECT_RETRY_ATTEMPTS', 3),
    'CONNECT_RETRY_DELAY_SECONDS': get_int_env('CONNECT_RETRY_DELAY_SECONDS', 1)
}

# ------- Scheduler -------
ACTIVE_MODE_DURATION_MINUTES = get_int_env('ACTIVE_MODE_DURATION_MINUTES', 10)
CREATIVE_RESPONSES_LIMIT = get_int_env('CREATIVE_RESPONSES_LIMIT', 7)

fake = Faker("ru_RU")

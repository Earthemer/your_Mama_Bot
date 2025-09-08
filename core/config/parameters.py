import logging
import random

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
    "long_term_memory",
    "message_log",
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
MORNING_GATHERING_HOUR = get_int_env('MORNING_GATHERING_HOUR', 8)
MORNING_GATHERING_MINUTE = get_int_env('MORNING_GATHERING_MINUTE', 50)
MORNING_ONLINE_DURATION = get_int_env('MORNING_ONLINE_DURATION', 10
                                      )
DAY_GATHERING_HOUR = get_int_env('DAY_GATHERING_HOUR', 13)
DAY_GATHERING_MINUTE = get_int_env('DAY_GATHERING_MINUTE', 0)
DAY_ONLINE_DURATION = get_int_env('DAY_ONLINE_DURATION', 15)

EVENING_GATHERING_HOUR = get_int_env('EVENING_GATHERING_HOUR', 19)
EVENING_GATHERING_MINUTE = get_int_env('EVENING_GATHERING_MINUTE', 0)
EVENING_ONLINE_DURATION = get_int_env('EVENING_ONLINE_DURATION', 20)

RANDOM_DAY_CHANCE_PERCENT = get_int_env('RANDOM_DAY_CHANCE_PERCENT', 15)
RANDOM_NIGHT_CHANCE_PERCENT = get_int_env('EVENING_GATHERING_MINUTE', 10)

RANDOM_GATHERING_DURATION = get_int_env('RANDOM_GATHERING_DURATION', 10)
RANDOM_ONLINE_DURATION_DAY = get_int_env('RANDOM_ONLINE_DURATION_DAY', 10)
RANDOM_ONLINE_DURATION_NIGHT = get_int_env('RANDOM_ONLINE_DURATION_NIGHT', 10)

RANDOM_DAY_HOUR = get_int_env('RANDOM_DAY_HOUR', 16)
RANDOM_DAY_MINUTE = get_int_env('RANDOM_DAY_MINUTE', 0)
RANDOM_NIGHT_HOUR  = get_int_env('RANDOM_NIGHT_HOUR', 23)
RANDOM_NIGHT_MINUTE = get_int_env('RANDOM_NIGHT_MINUTE', 0)

GATHERING_DURATION_MINUTES = get_int_env('GATHERING_DURATION_MINUTES', 15)
ONLINE_SESSION_DURATION_MINUTES = get_int_env('ONLINE_SESSION_DURATION_MINUTES', 20)

# ------- Faker -------
fake = Faker("ru_RU")

# ------- REDIS -------
REDIS_HOST = get_str_env('REDIS_HOST', 'localhost')
REDIS_PORT = get_int_env('REDIS_PORT', 6379)
CONFIG_CACHE_TTL = get_int_env('CONFIG_CACHE_TTL', 3600)

# ------- OPERATOR -------
PASSIVE_MODE_CHANCE = get_int_env('PASSIVE_MODE_CHANCE', 20)
ONLINE_MODE_REPLY_LIMIT = get_int_env('ONLINE_MODE_REPLY_LIMIT', 10)
ONLINE_MODE_USER_COOLDOWN_SECONDS = get_int_env('ONLINE_MODE_USER_COOLDOWN_SECONDS', 60)
ONLINE_MODE_BATCH_THRESHOLD = get_int_env('ONLINE_MODE_BATCH_THRESHOLD', 3)
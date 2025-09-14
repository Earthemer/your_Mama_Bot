import logging

from aiogram import Router, F, types, Bot
from aiogram.enums import ChatType

from core.database.postgres_client import AsyncPostgresManager
from core.database.redis_client import RedisClient
from core.config.exceptions import ListenerError
from core.config.logging_config import log_error
from core.operator import Operator
from core.config.parameters import CONFIG_CACHE_TTL

logger = logging.getLogger(__name__)

router = Router(name='message_listener')

@router.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    F.text,
)
@log_error
async def message_listener(
    message: types.Message,
    db: AsyncPostgresManager,
    redis: RedisClient,
    operator: Operator,
    bot: Bot,
):
    """
    Главный слушатель сообщений в группах.

    1. Игнорирует свои сообщения.
    2. Проверяет наличие конфига (с кэшем в Redis).
    3. Получает config и participant (config берётся из Redis, если есть).
    4. Пропускает заигноренных участников.
    5. Передаёт управление Operator.
    """

    chat_id = message.chat.id
    user_id = message.from_user.id

    if user_id == bot.id:
        return

    config_exists_key = f"config_exists:{chat_id}"
    config_data_key = f"config_data:{chat_id}"

    if not await redis.get_flag(config_exists_key):
        config = await db.get_mama_config(chat_id)
        if not config:
            return
        await redis.set_flag(config_exists_key, True, ttl_seconds=CONFIG_CACHE_TTL)
        await redis.set_json(config_data_key, config, CONFIG_CACHE_TTL)
    else:
        raw_config = await redis.get_json(config_data_key)
        if raw_config:
            config = raw_config
        else:
            config = await db.get_mama_config(chat_id)
            if not config:
                await redis.delete(config_exists_key)
                return
            await redis.set_json(config_data_key, config, CONFIG_CACHE_TTL)

    config_id = config["id"]

    try:
        participant = await db.get_participant(config_id, user_id)
    except Exception as e:
        raise ListenerError(f"Ошибка при получении participant {chat_id}:{user_id} - {e}") from e

    if participant and participant.get("is_ignored"):
        return

    await operator.handle_message(
        message=message,
        config=config,
        participant=participant,
    )










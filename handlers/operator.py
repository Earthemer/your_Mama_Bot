import logging

from core.database.redis_client import RedisClient

logger = logging.getLogger(__name__)


def _is_direct_mention(message) -> bool:
    """
    Проверка, было ли прямое обращение к боту.
    Тут можно гибко расширять (по @username, ключевым словам и т.д.)
    """
    if not message.text:
        return False
    return "@your_bot_username" in message.text


class Operator:
    """
    Оператор распределяет входящие сообщения:
    - прямые упоминания → direct_queue
    - фоновый шум → background_queue (только если разрешено)
    """
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def handle_message(self, message):
        """
        Обработка сообщения:
        - раскладывает по очередям
        - учитывает флаг "разрешён сбор фона"
        """
        try:
            payload = {
                "user_id": message.from_user.id,
                "chat_id": message.chat.id,
                "text": message.text,
                "timestamp": message.date.timestamp()
            }
            is_direct = _is_direct_mention(message)

            if is_direct:
                queue = f"direct_queue:{message.chat.id}"
                await self.redis.enqueue(queue, payload)
                logger.debug(f"Direct: {payload['text']} → {queue}")

            else:
                is_bg_enabled = await self.redis.get_flag(f"is_background_enabled:{message.chat.id}")
                if is_bg_enabled:
                    queue = f"background_queue:{message.chat.id}"
                    await self.redis.enqueue(queue, payload)
                    await self.redis.trim_queue(queue, max_len=50)
                    logger.debug(f"Background: {payload['text']} → {queue}")

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения оператором: {e}", exc_info=True)


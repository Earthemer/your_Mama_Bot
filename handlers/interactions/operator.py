import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.enums import  ChatType

from core.database import AsyncDatabaseManager
from core.config import parameters

logger = logging.getLogger(__name__)
router = Router()

@router.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    F.text
)
async def mama_listener(message: types.Message, state: FSMContext, db: AsyncDatabaseManager):
    """Главный хендлер, который "слушает" чат и реагирует на упоминание."""
    config = await db.get_mama_config(message.chat.id)
    if not config:
        return

    bot_name_in_message = config['bot_name'].lower() in message.text.lower()
    if not bot_name_in_message:
        return

    await message.reply(f"Я слышу, что ты упомянул мое имя, {config['bot_name']}!")
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.enums import ChatType

from core.database import AsyncDatabaseManager
from core.llm_service import LLMManager

from handlers.interactions import active_mode, waiting_mode, acquaintance

logger = logging.getLogger(__name__)
router = Router()

@router.message(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),
    F.text
)
async def mama_listener_operator(
    message: types.Message,
    state: FSMContext,
    bot: Bot,
    db: AsyncDatabaseManager,
    llm: LLMManager
):
    """
    Определяет режим и передает управление соответствующему сервису.
    """
    if not (config := await db.get_mama_config(message.chat.id)):
        return

    if not (participant := await db.get_participant(config['id'], message.from_user.id)) and participant.get('is_ignored'):
        return

    storage = state.storage
    storage_key = StorageKey(bot_id=bot.id, chat_id=message.chat.id, user_id=bot.id)
    mode_data = await storage.get_data(key=storage_key)
    current_mode = mode_data.get('mode', 'waiting')

    if not participant:
        await acquaintance.start_acquaintance(message, state, db, llm, config)
    elif current_mode == 'active':
        await active_mode.process_message(message, state, db, llm, config, participant)
    elif current_mode == 'waiting':
        await waiting_mode.process_message(message, state, db, llm, config, participant)
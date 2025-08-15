from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from core.database import AsyncDatabaseManager
from core.llm_service import LLMManager

async def start_acquaintance(
    message: types.Message,
    state: FSMContext,
    db: AsyncDatabaseManager,
    llm: LLMManager,
    config: dict,
):
    await message.reply("РЕЖИМ: ЗНАКОМСТВО. Получил твое сообщение.")
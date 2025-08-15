from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from core.database import AsyncDatabaseManager
from core.llm_service import LLMManager

async def process_message(
    message: types.Message,
    state: FSMContext,
    db: AsyncDatabaseManager,
    llm: LLMManager,
    config: dict,
    participant: dict
):
    await message.reply("РЕЖИМ: Пассивый. Получил твое сообщение.")
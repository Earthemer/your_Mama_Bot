import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType
from core.database import AsyncDatabaseManager
from core.exceptions import DatabaseConnectionError
from keyboards.setup_kb import get_setup_keyboard

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def handle_start(message: types.Message, db: AsyncDatabaseManager):
    """Обрабатывает команду /start.
    Проверяет, есть ли конфигурация для этого чата."""

    chat_id = message.chat.id
    logger.debug(f"Получена команда /start в чате {chat_id}")

    try:
        config = await db.get_mama_config(chat_id=chat_id)
    except DatabaseConnectionError as e:
        logger.error(f"Не удалось проверить конфиг для чата {chat_id}: {e}")
        await message.answer(
            "Ой, не могу заглянуть в свою записную книжку. Пожалуйста, попробуйте позже, пока я ищу очки.")
        return

    if config:
        bot_name = config.get('bot_name', 'Мама')
        await message.answer(f"Я уже здесь и слежу за порядком. Можете звать меня {bot_name}.")
    else:
        await message.answer(
            "Привет! Похоже, в этой семье еще нет мамы. Давайте это исправим!",
            reply_markup=get_setup_keyboard()
        )

@router.message(Command('clean'))
async def handle_clean(message: types.Message, db: AsyncDatabaseManager):
    """
    Обрабатывает команду /clean для сброса настроек бота в чате.
    Доступно только администраторам в группах.
    """
    chat_id = message.chat.id
    logger.debug(f"Получена команда /clean в чате {chat_id} от пользователя {message.from_user.id}")

    if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await message.answer("Эта команда работает только в групповых чатах.")
        return
    chat_member = await message.bot.get_chat_member(
        chat_id=chat_id,
        user_id=message.from_user.id
    )
    if chat_member.status not in ["creator", "administrator"]:
        await message.answer("Только администраторы могут сбрасывать мои настройки.")
        return

    # 3. Основная логика: удаление из БД
    try:
        deleted_rows = await db.delete_mama_config(chat_id=chat_id)
        if deleted_rows > 0:
            await message.answer(
                "Все мои настройки для этого чата были сброшены. Можете настроить меня заново через /start.")
        else:
            await message.answer("Для этого чата и так не было никаких настроек.")
    except DatabaseConnectionError:
        await message.answer("Не могу связаться со своей записной книжкой... Попробуйте позже.")
        return


@router.callback_query(F.data == "cancel_setup")
async def cancel_dialog(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие на кнопку отмены.
    """
    current_state = await state.get_state()
    if current_state is None:
        await callback.message.delete()
        await callback.answer()
        return

    await state.clear()
    await callback.answer("Настройка отменена.")
    await callback.message.edit_text("Действие отменено. Если передумаете, используйте команду /start.")

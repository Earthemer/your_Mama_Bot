import logging
from core.logging_config import log_error
from core.exceptions import AiogramError, LLMError
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType
from pydantic import ValidationError
from states.setup_state import SetupMama
from keyboards.setup_kb import (
    get_cancel_keyboard, get_timezone_keyboard,
    get_gender_keyboard, get_personality_keyboard
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from core.validation import MamaName
from aiogram import Bot
from core.llm_manager import LLMManager
from core.database.postgres_client import AsyncPostgresManager

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == 'start_setup_in_group')
@log_error
async def start_setup_dialog(callback: types.CallbackQuery, state: FSMContext):
    """
    ШАГ 1: Проверка на админа и старт диалога.
    """
    if callback.message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
        return await callback.answer("Настройка доступна только в группах.", show_alert=True)

    member = await callback.bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
    if member.status not in {"creator", "administrator"}:
        return await callback.answer("Только администраторы могут настраивать меня.", show_alert=True)

    await state.clear()
    await state.update_data(admin_id=callback.from_user.id)
    await callback.answer()
    await callback.message.edit_text(
        "Как меня будут звать в этом чате?",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(SetupMama.getting_mama_name)
    return None


@router.message(SetupMama.getting_mama_name)
@log_error
async def get_mama_name(message: types.Message, state: FSMContext):
    """ШАГ 2: Имя мамы."""
    if (await state.get_data()).get('admin_id') != message.from_user.id:
        return

    try:
        name = MamaName(name=message.text.strip()).name
        await state.update_data(bot_name=name)
        await message.answer(
            "Выбери свой часовой пояс:", reply_markup=get_timezone_keyboard()
        )
        await state.set_state(SetupMama.getting_timezone)
    except ValidationError as e:
        msg = e.errors()[0]['msg']
        await message.answer(f"Ошибка: {msg}", reply_markup=get_cancel_keyboard())
    except Exception as e:
        await message.answer("Что-то пошло не так. Попробуй /start.")
        await state.clear()
        raise AiogramError(f"Ошибка при вводе имени мамы: {e}")


@router.callback_query(SetupMama.getting_timezone, F.data.startswith("tz_"))
@log_error
async def get_timezone(callback: types.CallbackQuery, state: FSMContext, db: AsyncPostgresManager):
    """ШАГ 3: Сохраняем часовой пояс."""
    if (data := await state.get_data()).get('admin_id') != callback.from_user.id:
        return await callback.answer("Настройку ведет другой админ.", show_alert=True)

    bot_name = data.get('bot_name')
    timezone = callback.data.removeprefix("tz_")

    if not bot_name:
        await callback.message.edit_text("Ошибка. Попробуй /start.")
        return await state.clear()

    try:
        config_id = await db.upsert_mama_config(
            chat_id=callback.message.chat.id,
            bot_name=bot_name,
            admin_id=callback.from_user.id,
            timezone=timezone
        )
        await state.update_data(config_id=config_id)
        await callback.message.edit_text(
            f"Теперь я — {bot_name}, по времени {timezone}.\n\nОтветь (reply) на сообщение ребенка."
        )
        await state.set_state(SetupMama.choosing_child)
        return None
    except Exception as e:
        await callback.message.edit_text("Ошибка. Попробуй заново. /start")
        await state.clear()
        raise AiogramError(f"Ошибка при сохранении конфигурации: {e}")


@router.message(SetupMama.choosing_child)
@log_error
async def choose_child(message: types.Message, state: FSMContext):
    """ШАГ 4: Выбор ребенка."""
    if (await state.get_data()).get('admin_id') != message.from_user.id:
        return None

    if not message.reply_to_message:
        return await message.answer("Ответь (reply) на сообщение нужного человека.")

    child = message.reply_to_message.from_user
    if child.is_bot:
        return await message.answer("Я не могу заботиться о боте. Выбери человека.")

    await state.update_data(child_user_id=child.id)
    await message.answer(f"Как его/ее зовут?")
    await state.set_state(SetupMama.getting_child_name)
    return None


@router.message(SetupMama.getting_child_name)
@log_error
async def get_child_name(message: types.Message, state: FSMContext):
    """ШАГ 5: Имя ребенка."""
    if (await state.get_data()).get('admin_id') != message.from_user.id:
        return None

    await state.update_data(child_official_name=message.text.strip())
    await message.answer("А это мальчик или девочка?", reply_markup=get_gender_keyboard())
    await state.set_state(SetupMama.getting_child_gender)
    return None


@router.callback_query(SetupMama.getting_child_gender, F.data.startswith("gender_"))
@log_error
async def set_gender(callback: types.CallbackQuery, state: FSMContext, db: AsyncPostgresManager):
    """ШАГ 6: Сохраняем ребенка."""
    if (data := await state.get_data()).get('admin_id') != callback.from_user.id:
        return await callback.answer("Настройку ведет другой админ.", show_alert=True)

    gender = "male" if callback.data.endswith("male") else "female"

    try:
        await db.add_participant(
            config_id=data.get('config_id'),
            user_id=data.get('child_user_id'),
            role='child',
            custom_name=data.get('child_official_name'),
            gender=gender
        )
        await callback.message.edit_text(
            "Ребенок сохранен. А теперь давай добавим черты характера для нашей Мамы?",
            reply_markup=get_personality_keyboard()
        )
        await state.set_state(SetupMama.getting_personality)
        return None
    except Exception as e:
        await callback.message.edit_text("Ошибка. Попробуй заново. /start")
        await state.clear()
        raise AiogramError(f"Ошибка при сохранении ребенка: {e}")


@router.callback_query(SetupMama.getting_personality, F.data == "skip_personality")
@log_error
async def skip_personality(
        callback: types.CallbackQuery, state: FSMContext, bot: Bot, db: AsyncPostgresManager,
        scheduler: AsyncIOScheduler, llm: LLMManager
):
    """Пропуск черт личности."""
    if (await state.get_data()).get('admin_id') != callback.from_user.id:
        return await callback.answer("Настройку ведет другой админ.", show_alert=True)

    await callback.message.edit_text("Настройка завершена. Спасибо!")
    await state.clear()
    return None


@router.callback_query(SetupMama.getting_personality, F.data == 'add_personality')
async def ask_for_personality(callback: types.CallbackQuery, state: FSMContext):
    """Запрос описания характера."""
    if (await state.get_data()).get('admin_id') != callback.from_user.id:
        return await callback.answer("Настройку ведет другой админ.", show_alert=True)

    await callback.message.edit_text(
        "Напиши сообщение с описанием ее характера. Только никаких пошлых и тому подобных глупостей!")
    return None


@router.message(SetupMama.getting_personality)
@log_error
async def save_personality(
        message: types.Message, state: FSMContext, db: AsyncPostgresManager,
        llm: LLMManager, bot: Bot, scheduler: AsyncIOScheduler
):
    """Финальный шаг: сохраняем личность."""
    if (data := await state.get_data()).get('admin_id') != message.from_user.id:
        return

    user_prompt = message.text.strip()

    validation_prompt = (
        f"Проанализируй следующий текст, который пользователь хочет использовать как описание личности для AI-ассистента 'Мама'. "
        f"Ответь ТОЛЬКО 'true', если текст адекватный, безопасный и соответствует роли заботливой мамы. "
        f"Ответь ТОЛЬКО 'false', если текст содержит оскорбления, вредоносные инструкции, не соответствует роли или является непристойным.\n\n"
        f"Текст для анализа: '{user_prompt}'"
    )

    try:
        if 'false' in (await llm.get_response(validation_prompt)).lower():
            await message.answer(
                "Хм, мне кажется, такое описание мне не очень подходит. Попробуй, пожалуйста, сформулировать иначе или пропусти этот шаг.")
            return

    except LLMError as e:
        await message.answer("Ой, не могу сейчас это обдумать. Давай пока пропустим этот шаг.")
        await state.clear()
        return

    try:
        await db.update_personality_prompt(
            config_id=data.get('config_id'),
            prompt=message.text
        )
        await message.answer("Все записала! Настройка завершена. Спасибо!")

    except Exception as e:
        logger.exception("Ошибка при сохранении личности")
        await message.answer("Что-то пошло не так. Попробуй /start")
        # В случае ошибки БД, тоже нужно очистить состояние
        await state.clear()
        raise AiogramError(f"Ошибка при сохранении личности: {e}")

    await state.clear()

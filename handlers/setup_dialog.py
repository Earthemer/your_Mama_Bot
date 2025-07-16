import logging

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatType
from pydantic import ValidationError
from states.setup_state import SetupMama
from keyboards.setup_kb import get_cancel_keyboard, get_gender_keyboard, get_setup_keyboard
from core.validation import MamaName
from core.database import AsyncDatabaseManager

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == 'start_setup_in_group')
async def start_setup_dialog(callback: types.CallbackQuery, state: FSMContext):
    """
    ШАГ 1: Начало диалога.
    Вызывается при нажатии на кнопку "Настроить в групповом чате".
    """
    if callback.message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await callback.answer("Настройка возможна только в групповых чатах.", show_alert=True)
        return

    chat_member = await callback.bot.get_chat_member(
        chat_id=callback.message.chat.id,
        user_id=callback.from_user.id
    )
    if chat_member.status not in ["creator", "administrator"]:
        await callback.answer("Только администраторы могут настраивать меня.", show_alert=True)
        return

    await state.clear()

    await state.update_data(admin_id=callback.from_user.id)

    await callback.answer()

    await callback.message.edit_text(
        "Отлично! Начинаем настройку. Как меня будут звать в этом чате?",
        reply_markup=get_cancel_keyboard()
    )

    await state.set_state(SetupMama.getting_mama_name)


@router.message(SetupMama.getting_mama_name)
async def get_mama_name(message: types.Message, state: FSMContext):
    """
    ШАГ 2: Получение имени Мамы.
    """
    data = await state.get_data()
    print(f"DEBUG: Получены данные из состояния: {data}")
    print(f"DEBUG: Тип данных: {type(data)}")

    # Проверяем, что данные - это словарь. Если нет, это критическая ошибка.
    if not isinstance(data, dict):
        logger.error(f"Критическая ошибка FSM: data не является словарем! Получено: {data}")
        await message.answer("Ой, что-то в голове перепуталось. Давайте попробуем еще раз.")
        await state.clear()
        await message.answer(
            "Похоже, в этой семье еще нет мамы. Давайте это исправим!",
            reply_markup=get_setup_keyboard()
        )
        return

    admin_id = data.get('admin_id')

    if message.from_user.id != admin_id:
        return

    try:
        validate_name = MamaName(name=message.text.strip())
        mama_name = validate_name.name

        await state.update_data(mama_name=mama_name)

        await message.answer(
            f"Теперь я — {mama_name}!\n"
            f"Хочешь выбрать моего сыночка или дочку?\n\n"
            f"Просто ответь (reply) на любое сообщение от этого человека в чате, и я всё пойму 😉",
            parse_mode="HTML"
        )

        await state.set_state(SetupMama.choosing_child)

    except ValidationError as e:

        error_message = e.errors()[0]['msg']
        await message.answer(f"Ошибка: {error_message}\nПожалуйста, попробуй еще раз.")
        return

@router.message(SetupMama.choosing_child)
async def choose_child(message: types.Message, state: FSMContext):
    """
    ШАГ 3: Выбор "ребенка".
    """
    data = await state.get_data()
    admin_id = data.get('admin_id')

    if message.from_user.id != admin_id:
        return

    if not message.reply_to_message:
        await message.answer("Пожалуйста, нажми 'ответить' (reply) на сообщение нужного человека.")
        return

    child_user = message.reply_to_message.from_user

    if child_user.is_bot:
        await message.answer("Я не могу заботиться о другом боте. Выбери обычного пользователя.")
        return

    await state.update_data(
        child_id=child_user.id,
        child_name=child_user.first_name
    )

    await message.answer(
        f"Конечно! Кто тут мой пирожочек? — {child_user.first_name}. А это мальчик или девочка?",
        reply_markup=get_gender_keyboard()
    )
    await state.set_state(SetupMama.choosing_gender)

@router.callback_query(SetupMama.choosing_gender, F.data.startswith("gender_"))
async def choose_gender_and_save(callback: types.CallbackQuery, state: FSMContext, db: AsyncDatabaseManager):
    """
    ШАГ 4: Выбор пола и сохранение в БД.
    Ловит нажатие на кнопки "gender_male" или "gender_female".
    """
    # Определяем пол по callback_data
    gender = "male" if callback.data == "gender_male" else "female"

    user_data = await state.get_data()
    mama_name = user_data.get('mama_name')
    child_id = user_data.get('child_id')
    child_name = user_data.get('child_name')

    if not all([mama_name, child_id, child_name]):
        await callback.message.edit_text("Ой, я что-то забыла в процессе... Давай начнем настройку сначала. /start")
        await state.clear()
        return

    try:
        await db.upsert_mama_config(
            chat_id=callback.message.chat.id,
            bot_name=mama_name,
            child_user_id=child_id,
            child_first_name=child_name,
            gender=gender
        )
        gender_text = 'сыночком' if gender == 'male' else 'доченькой'
        await callback.message.edit_text(
            f"Настройка завершена! Я — {mama_name}, и я буду присматривать за моим {gender_text} {child_name}!")

    except Exception as e:
        logger.error(f"Финальная ошибка сохранения конфига для чата {callback.message.chat.id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "Ой, что-то пошло не так с моей записной книжкой... Попробуй настроить меня заново через /start")

    finally:
        await state.clear()




# keyboards/setup_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_setup_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="👩🏻‍🦰 Настроить для личного чата",
            callback_data='start_setup_in_private'
        ),
        InlineKeyboardButton(
            text="👨‍👩‍👦 Настроить в групповом чате",
            callback_data = 'start_setup_in_group'
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_setup"
        )
    )
    return builder.as_markup()

def get_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Мальчик 👦", callback_data="gender_male"),
        InlineKeyboardButton(text="Девочка 👧", callback_data="gender_female")
    )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_setup")
    )
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="❌ Отменить настройку",
        callback_data="cancel_setup"
    ))
    return builder.as_markup()


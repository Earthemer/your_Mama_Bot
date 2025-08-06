# keyboards/setup_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_setup_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="👩🏻‍🦰 Приватный режим",
            callback_data='start_setup_in_private'
        ),
        InlineKeyboardButton(
            text="👨‍👩‍👦 Групповой чат",
            callback_data='start_setup_in_group'
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_setup"
        )
    )
    return builder.as_markup()


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора часового пояса."""
    builder = InlineKeyboardBuilder()

    timezones = {
        "Калининград (UTC+2)": "Europe/Kaliningrad",
        "Москва (UTC+3)": "Europe/Moscow",
        "Самара (UTC+4)": "Europe/Samara",
        "Екатеринбург (UTC+5)": "Asia/Yekaterinburg",
        "Омск (UTC+6)": "Asia/Omsk",
        "Красноярск (UTC+7)": "Asia/Krasnoyarsk"
    }

    for text, callback_data in timezones.items():
        builder.button(text=text, callback_data=f"tz_{callback_data}")

    builder.adjust(2)

    builder.row(InlineKeyboardButton(text="❌ Отменить настройку", callback_data="cancel_setup"))

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

def get_personality_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопками Да/Нет для добавления личности."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Да, добавить", callback_data="add_personality")
    builder.button(text="⏩ Пропустить", callback_data="skip_personality")
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="❌ Отменить настройку",
        callback_data="cancel_setup"
    ))
    return builder.as_markup()

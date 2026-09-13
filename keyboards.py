from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def start_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Начать", callback_data="start_quiz")
    return builder.as_markup()


def next_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Далее", callback_data="next_question")
    return builder.as_markup()


def confirm_reset_db_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="confirm_reset_db")
    builder.button(text="Отмена", callback_data="cancel_reset_db")
    return builder.as_markup()


def confirm_delete_button() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data="confirm_delete")
    builder.button(text="Отмена", callback_data="cancel_delete")
    return builder.as_markup()
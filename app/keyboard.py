from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.database.requests import get_models_by_type




start_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text = "Как пользоваться?"), KeyboardButton(text = "Выбрать модель")],
    [KeyboardButton(text = "Узнать траты"), KeyboardButton(text = "На главную")]
],
resize_keyboard = True,
input_field_placeholder = "Выберите пункт меню"
)

model_types_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text = "Текст", callback_data = "text")],
        [InlineKeyboardButton(text = "Изображение", callback_data = "image")],
        [InlineKeyboardButton(text = "Аудио", callback_data = "audio")],
        [InlineKeyboardButton(text = "Видео", callback_data = "video")]
    ]
)

async def ai_models_inline_keyboard(model_type: str):
    all_models = await get_models_by_type(model_type = model_type)
    keyboard = InlineKeyboardBuilder()

    for model in all_models:
        keyboard.add(InlineKeyboardButton(text = model.model_name.split("/")[1], callback_data = f"info_{model_type}_{model.model_name}"))

    keyboard.add(InlineKeyboardButton(text = "Назад", callback_data = "back_to_select_model_type"))
    return keyboard.adjust(2).as_markup()

async def ai_model_info_keyboard(model_type: str, model_name: str):
    '''
    Клавиатура, появляющаяся при выборе конткретной модели ии.
    '''
    keyboard = InlineKeyboardBuilder(
        markup = [
            [InlineKeyboardButton(text = "Начать общение", callback_data = f"start_dialogue_{model_type}_{model_name}")],
            [InlineKeyboardButton(text = "Назад", callback_data = model_type)]
        ]
    )
    return keyboard.adjust(2).as_markup()

in_dialogue_keyboard = ReplyKeyboardMarkup(
    keyboard = [
        [KeyboardButton(text = "Хочу прикрепить файл(ы)")],
        [KeyboardButton(text = "Новый диалог"), KeyboardButton(text = "Выйти")]
    ],
    resize_keyboard=True
)

collecting_files_keyboard = ReplyKeyboardMarkup(
    keyboard = [
        [KeyboardButton(text = "Я закончил")]
    ]
)
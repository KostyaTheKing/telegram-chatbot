from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram import Router , html, F
from aiogram.fsm.context import FSMContext
import app.keyboard
import app.database.requests as rq
from app.user_states import Chatting
from app.ai_requests import generate_response
from app.parse_files import parse_attachment, correct_markdown_v2_string, check_previous_messages
from config import ALLOWED_USERS, ADMIN_USERS, MAX_MESSAGE_HISTORY, MAX_IMAGE_HISTORY, MAX_PDF_HISTORY
from textwrap import dedent, wrap
from asyncio import Lock, sleep
from collections import defaultdict

router = Router()
user_locks = defaultdict(Lock)

router.message.filter(F.from_user.username.in_(ALLOWED_USERS))

@router.message(F.text.in_({"/start", "На главную", "Выйти"}))
async def command_start_help_handler(message: Message) -> None:
    """
    Этот обработчик работает с командами start и help. Приветствует пользователя и описывает функционал экранной клавиатуры.
    """
    about_bot = dedent(f'''
    Привет, {html.bold(message.from_user.full_name)}! Бот готов к работе. Выберите интересующую вас опцию в клавиатуре ниже.

    > {html.italic("Как пользоваться?")} - выводит информацию о том, как работают запросы к ии и как работает бот.
    > {html.italic("Выбрать модель")} - перейти к выбору модели и начать диалог с ии.
    > {html.italic("Узнать траты")} - рассчитать количество потраченных денег за запросы к ии.
    > {html.italic("На главную")} - возвращает на главную страницу.
    ''')
    await message.answer(about_bot,
                         reply_markup = app.keyboard.start_keyboard)

@router.message(Command("help"), F.from_user.username.in_(ADMIN_USERS))
async def show_admin_commands(message: Message) -> None:
    '''
    Выводит список команд, доступных админу.
    '''
    text = dedent('''
        Вот список команд и их описание, доступные админу:
        Для добавления новых пользователей необходимо использовать команду /edit_users.
        Для просмотра трат пользователей, а также редактирования трат пользователей используется команда /edit_spendings.
        Вызовите команду, чтобы увидеть, как ей пользоваться.
        '''
    )
    await message.answer(text = text)

@router.message(Command("edit_users"), F.from_user.username.in_(ADMIN_USERS))
async def edit_users(message: Message, command: CommandObject) -> None:
    '''
    Позволяет удалять или добавлять пользователей и админов с помощью команды edit_users.
    Команда должна иметь вид: /edit_users add/remove user/admin some_tg_username
    '''
    if (command.args is not None) and (len(command.args.split()) == 3):
        command_args = command.args.split()

        match command_args[0]:
            case "add":
                res = await rq.add_user(tg_username=command_args[2], role=command_args[1])
                await message.answer(text = "Пользователь успешно добавлен") if res else await message.answer(text = "Такой пользователь уже есть.")
            case "remove":
                res = await rq.remove_user(tg_username=command_args[2])
                await message.answer(text = "Пользователь успешно удалён") if res else await message.answer(text = "Такого пользователя нет.")
            case _:
                await message.answer(text = "Неправильная команда. Используйте add или remove.")
    else:
        await message.answer("Команда должна иметь вид: /edit_users add/remove user/admin some_tg_username")

@router.message(Command("edit_spendings"), F.from_user.username.in_(ADMIN_USERS))
async def edit_spendings(message: Message, command: CommandObject) -> None:
    '''
    Эта команда позволяет показать траты пользователей, а также обнулить траты при необходимости (можно за период).
    Команда /edit_spendings show покажет траты всех пользователей за весь период.
    Команда /edit_spendings show username покажет траты пользователя username за всё время.
    Команда /edit_spendings show username start end покажет траты пользователя username за период start-end. Вводить дату в формате yyyy-mm-dd
    Команда /edit_spendings remove username удалит все запросы пользователя из бд.
    Команда /edit_spendings remove username start end удалит запросы пользователя из бд за промежуток start-end. Вводить
    дату в формате yyyy-mm-dd
    '''

    help_message = dedent("""
    Команда /edit_spendings show покажет траты всех пользователей за весь период.
    Команда /edit_spendings show username покажет траты пользователя username за всё время.
    Команда /edit_spendings show username start end покажет траты пользователя username за период start-end. Вводить дату в формате yyyy-mm-dd
    Команда /edit_spendings remove username удалит все запросы пользователя из бд.
    Команда /edit_spendings remove username start end удалит запросы пользователя из бд за промежуток start-end. Вводить дату в формате yyyy-mm-dd
    """)

    if (command.args is not None):
        command_args = command.args.split()
        args_len = len(command_args)
        match command_args[0]:
            case "show":
                match args_len:
                    case 1:
                        all_user_info = await rq.show_all_users_and_money_spent()
                        all_user_info = sorted(all_user_info, key = lambda x: x[0])
                        all_user_info = list(map(lambda x: "{0} - {1:.2f}$".format(x[0], x[1]), all_user_info))
                        text = "\n".join(["Вот траты пользователей:"] + all_user_info)
                        await message.answer(text=text)
                        return
                    case 2:
                        username = command_args[1]
                        money_spent = await rq.calculate_spent_money(tg_username = username)
                        await message.answer(text = f"{username}: {money_spent}$")
                        return
                    case 4:
                        username = command_args[1]
                        start = command_args[2]
                        end = command_args[3]
                        money_spent = await rq.calculate_spent_money(username, start, end)
                        await message.answer(text=f"Пользователь {username} в период с {start} по {end} потратил - {money_spent:.2f}$")
                        return
            case "remove":
                match args_len:
                    case 2:
                        username = command_args[1]
                        await rq.remove_user_requests(username)
                        await message.answer(text = f"Запросы пользователя успешно удалены.")
                        return
                    case 4:
                        username = command_args[1]
                        start = command_args[2]
                        end = command_args[3]
                        await rq.remove_user_requests(username, start, end)
                        await message.answer(text = f"Запросы пользователя в период с {start} по {end} были успешно удалены.")
                        return
    await message.answer(text = help_message)


@router.message(F.text == "Как пользоваться?")
async def how_to_use_the_bot(message: Message) -> None:
    '''
    Выводит информацию о том, как пользоваться ботом, а также, как работает ии.
    '''

    about_bot_and_ai = dedent(f'''
    Кнопка {html.italic("Выбрать модель")} позволяет выбрать интересующую Вас модель по типу.
    Существует 4 типа моделей:
    - {html.bold("для текста")} - принимают текст, файлы и фотографии и генерируют текст.
    - {html.bold("для изображений")} - принимают текст, фотографии и генерируют изображения.
    - {html.bold("для аудио")} - пока что недоступны.
    - {html.bold("для видео")} - пока что недоступны.
    При выборе конкретной модели создаётся новый диалог. ИИ помнит последние 20 отправленных Вам сообщений в этом диалоге.
    Для того чтобы прикрепить фотографию или файл, нажмите {html.bold("Хочу прикрепить файл(ы)")}.
    Не пишите никакие запросы, пока не закончите прикреплять файлы. Дождитесь окончания загрузки файлов. После загрузки файлов можно писать запрос.
    Как рассчитывается стоимость запросов к ии? Существует три типа цены:
    - Цена за {html.bold("обычный запрос")}.
    - Цена за {html.bold("кэшированный запрос")}.
    - Цена за {html.bold("ответ модели")}.
    При ведении одного диалога вся история сообщений пересылается ИИ для генерации ответа. Часть запроса может оказаться кэшированной.
    Если хочется сменить тему общения с ИИ, то лучше создать новый диалог, чтобы не пересылать много старых сообщений.
    ''')

    await message.answer(
        text = about_bot_and_ai
    )

@router.message(F.text == "Узнать траты")
async def calculate_money_spent(message: Message) -> None:
    '''
    Рассчитывает количество денег, потраченных на общение с ИИ в долларах.
    '''
    total_money_spent = await rq.calculate_spent_money(message.from_user.username)
    await message.answer(f"Вы всего потратили {total_money_spent:.2f}$")

@router.message(F.text == "Выбрать модель")
async def choose_model_type(message: Message):
    '''
    Отправляет сообщение с inline кнопками для выбора типа модели.
    '''
    await message.answer(
        text = "Какую модель будем использовать сегодня?",
        reply_markup = app.keyboard.model_types_keyboard
    )

@router.callback_query(F.data.in_({"text", "image", "audio", "video"}))
async def text_models(callback: CallbackQuery):
    '''
    Из базы данных достаёт доступные виды моделей по типу.
    '''
    await callback.answer()
    await callback.message.edit_text(
        text = "Какую модель вы хотите выбрать?\n",
        reply_markup = await app.keyboard.ai_models_inline_keyboard(callback.data)
    )

@router.callback_query(F.data == "back_to_select_model_type")
async def back_to_model_type_selection(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        text = "Какую модель будем использовать сегодня?",
        reply_markup = app.keyboard.model_types_keyboard
    )

@router.callback_query(F.data.startswith("info_"))
async def show_model_info(callback: CallbackQuery):
    '''
    Выводит информацию о конкретной модели: описание, цена. Также позволяет начать общение или вернуться назад.
    '''
    await callback.answer()
    _, model_type, model_name = callback.data.split("_")
    
    result = await rq.fetch_model_info(model_name)
    ai_model_info = result.scalar_one_or_none()
    input_cached_price = f"{ai_model_info.input_cached_price:.2f} $ / 1 миллион токенов" if not (ai_model_info.input_cached_price is None) else "Нет"

    message_text = dedent(f'''
    {ai_model_info.description}
    Цена ввода: {ai_model_info.input_price:.2f} $ / 1 миллион токенов
    Цена кэшированного ввода: {input_cached_price}
    Цена вывода: {ai_model_info.output_price:.2f} $ / 1 миллион токенов
    ''')
    await callback.message.edit_text(
        text = message_text,
        reply_markup = await app.keyboard.ai_model_info_keyboard(model_type=model_type, model_name=model_name)
    )

@router.callback_query(F.data.startswith("start_dialogue"))
async def enter_into_ai_dialogue(callback: CallbackQuery, state: FSMContext):
    '''
    Начать диалог с ИИ.
    '''
    await callback.answer()
    _, _, model_type, model_name = callback.data.split("_")
    await state.set_state(Chatting.in_dialogue)
    await state.update_data(in_dialogue = {"model": (model_type, model_name)})
    await callback.message.answer(f"Можно начинать общение с {model_name}. Если хотите создать новый диалог, нажмите кнопку Новый диалог. Если хотите закончить общение, то нажмите Выйти.",
                                  reply_markup=app.keyboard.in_dialogue_keyboard
                                 )

@router.message(Chatting.in_dialogue, F.text == "Выйти")
async def exit_ai_dialogue(message: Message, state: FSMContext):
    '''
    Позволяет выйти из диалога с ИИ.
    '''
    model = await state.get_data()
    await state.clear()
    await message.answer(text = f"Вы вышли из диалога с {model["in_dialogue"]["model"][1]}",
                         reply_markup = app.keyboard.start_keyboard)

@router.message(Chatting.in_dialogue, F.text == "Новый диалог")
async def create_new_dialogue(message: Message, state: FSMContext):
    '''
    Позволяет создать новый диалог с ИИ.
    '''
    ai_model_and_dialogue_data = await state.get_data()
    model_type, model_name = ai_model_and_dialogue_data["in_dialogue"]["model"]
    await state.update_data(in_dialogue = {"model": (model_type, model_name), "previous_messages": []})
    await message.answer("Новый диалог успешно создан.")

@router.message(Chatting.in_dialogue, F.text == "Хочу прикрепить файл(ы)")
async def get_ready_for_files_from_user(message: Message, state: FSMContext):
    '''
    Переводит пользователя в состояние сбора файлов.
    '''
    await state.set_state(Chatting.collecting_files)
    await message.answer("Можете прикреплять файлы (текстовый запрос здесь писать не надо). Когда все файлы загрузятся, нажмите кнопку \"Я закончил\".",
                         reply_markup=app.keyboard.collecting_files_keyboard)

@router.message(Chatting.collecting_files, F.text == "Я закончил")
async def finish_collecting_files_from_user(message: Message, state: FSMContext):
    '''
    Заканчивает сбор файлов от пользователя и добавляет все файлы к in_dialogue state.
    '''
    collected_files = await state.get_data()
    collected_files = collected_files.get("collecting_files", [])
    await state.update_data(collecting_files = [])
    await state.set_state(Chatting.in_dialogue)
    in_dialogue_data = await state.get_data()
    in_dialogue_data = in_dialogue_data["in_dialogue"]
    in_dialogue_data["collected_files"] = collected_files if (current_files := in_dialogue_data.get("collected_files", None)) is None else current_files + collected_files
    user_locks.pop(message.from_user.id, None)
    await state.update_data(in_dialogue = in_dialogue_data)
    await message.answer("Отлично, теперь можете писать свой запрос.", reply_markup=app.keyboard.in_dialogue_keyboard)

@router.message(Chatting.collecting_files, F.photo | F.document)
async def collecting_files_from_user(message: Message, state: FSMContext) -> None:
    '''
    Собирает файлы от пользователя до тех пор, пока пользователь не нажмёт кнопку "Я закончил".
    '''
    user_lock = user_locks[message.from_user.id]
    async with user_lock:
        collected_files = await state.get_data()
        collected_files = collected_files.get("collecting_files", [])
        processed_attachment = await parse_attachment(message)
        if processed_attachment is not None:
            collected_files.append(processed_attachment)
            await state.update_data(collecting_files = collected_files)
        else:
            await message.answer("Этот тип файла не поддерживается.")

@router.message(Chatting.in_dialogue)
async def send_message_to_ai(message: Message, state: FSMContext):
    '''
    Отправляет запросы пользователя искусственному интеллекту.
    '''
    ai_model_and_dialogue_data = await state.get_data()

    model_type, model_name = ai_model_and_dialogue_data["in_dialogue"]["model"]

    previous_messages = ai_model_and_dialogue_data["in_dialogue"].get("previous_messages", [])

    previous_messages = await check_previous_messages(
        previous_messages = previous_messages,
        max_amount_of_previous_messages = MAX_MESSAGE_HISTORY,
        store_pdfs_for_n_messages = MAX_PDF_HISTORY,
        store_photos_for_n_messages = MAX_IMAGE_HISTORY
    )

    attached_files = ai_model_and_dialogue_data["in_dialogue"].get("collected_files", [])
    
    await state.set_state(Chatting.waiting_for_response)
    try:
        response, previous_messages = await generate_response(user_request=message.text, ai_model=model_name, previous_messages=previous_messages, attached_files=attached_files)
        previous_messages.append({"role": "assistant", "content": response.output_text})
        await rq.store_money_spent_per_request(tg_username = message.from_user.username,
                                               money_spent = response.usage.cost,
                                               ai_model = model_name)

        response_output_text = await correct_markdown_v2_string(response.output_text)
        for output_text in wrap(response_output_text, 4096, replace_whitespace = False, break_long_words = False):
            try:
                await message.answer(output_text, parse_mode="MarkdownV2")
                await sleep(0.150)
            except Exception as e:
                print(e)
                await message.answer(output_text, parse_mode=None)
                await sleep(0.150)
        await state.set_state(Chatting.in_dialogue)
        await state.update_data(in_dialogue = {"model": (model_type, model_name), "previous_messages": previous_messages})
    except Exception as e:
        print(e)
        await message.answer("Возникла непредвиденная ошибка :(")
        await state.set_state(Chatting.in_dialogue)


@router.message(Chatting.waiting_for_response)
async def stop_user_from_sending_requests(message: Message) -> None:
    '''
    Предотвращает отправку новых запросов, пока пользователь не получит ответ.
    '''
    await message.answer("Подождите, Ваш запрос обрабатывается!")
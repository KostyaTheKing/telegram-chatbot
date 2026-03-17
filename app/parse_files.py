from aiogram.types import Message
import io
import base64
import re
from bisect import bisect_right
from docx import Document
from docx.table import Table

async def read_word_file(message: Message) -> tuple[str, str]:
    '''
    Читает word файлы. Передаётся message, из которого извлекается содержимое word файла.
    Функция возвращает кортеж, в котором помечено, что есть содержимое word файла - строка.
    Картинки не обрабатываются, но текст и таблицы - да.
    '''

    file_id = message.document.file_id

    document_content = message.document.file_name + "\n"

    document_buffer = io.BytesIO()

    await message.bot.download(file = file_id, destination = document_buffer)

    word_file_content = Document(document_buffer)

    document_buffer.close()

    for element in word_file_content.iter_inner_content():
        if isinstance(element, Table):
            for rows in element.rows:
                for cell in rows.cells:
                    document_content += cell.text + "\t"
                document_content += "\n"
            continue
        document_content += element.text + "\n"
    
    return ("str", document_content)

async def read_pdf_file(message: Message) -> tuple[str, dict[str, str]]:
    '''
    Возвращает готовое содержимое для openai api. Внутри pdf в виде строки, закодированной в base64.
    '''
    file_id = message.document.file_id
    file_name = message.document.file_name

    document_buffer = io.BytesIO()
    await message.bot.download(file = file_id, destination = document_buffer)
    b64encoded_pdf = base64.b64encode(document_buffer.getvalue()).decode("utf-8")
    document_buffer.close()

    return (
        "pdf",
        {
            "type": "input_file",
            "filename": file_name,
            "file_data": f"data:application/pdf;base64,{b64encoded_pdf}"
        }
    )

async def read_text_file(message: Message) -> tuple[str, str]:
    '''
    Парсит текстовые файлы. Вначале идёт название файла, а потом содержание файла.
    '''
    file_id = message.document.file_id

    document_content = message.document.file_name + "\n"

    document_buffer = io.BytesIO()

    await message.bot.download(file = file_id, destination = document_buffer)

    document_content += document_buffer.getvalue().decode("utf-8")

    document_buffer.close()

    return ("str", document_content)

async def parse_image_file(message: Message) -> tuple[str, dict[str, str]]:
    '''
    Преобразует изображения в base64 кодировку и создаёт image_url для openai api.
    '''
    if message.photo is not None:
        photo_id = message.photo[-1].file_id
    else:
        photo_id = message.document.file_id

    photo_buffer = io.BytesIO()

    await message.bot.download(photo_id, photo_buffer)

    b64encoded_photo = base64.b64encode(photo_buffer.getvalue()).decode("utf-8")

    photo_buffer.close()

    return ("img",
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{b64encoded_photo}"
            }
    )


async def parse_attachment(message: Message):
    '''
    Производит обработку прикреплённого файла в соответствии с его форматом.
    '''
    # Обрабатывает фото
    if message.photo is not None:
        return await parse_image_file(message)
    # Обрабатывает word документ
    elif (file_ext := message.document.file_name.split(".")[-1]) in ["docx", "doc"]:
        return await read_word_file(message)
    # Обрабатывает pdf документ
    elif file_ext == "pdf":
        return await read_pdf_file(message)
    elif file_ext in ["png", "jpeg", "jpg"]:
        return await parse_image_file(message)
    # Обрабатывает любой другой документ
    else:
        try:
            return await read_text_file(message)
        except:
            return None


async def check_previous_messages(previous_messages: list,
                                  max_amount_of_previous_messages: int,
                                  store_pdfs_for_n_messages: int,
                                  store_photos_for_n_messages: int
                                  ) -> list:
    '''
    Проверяет количество предыдущих сообщений, а также стоит ли дальше хранить информацию о файлах или фотографиях.
    '''

    def remove_extra_contents(message: dict, content_type: str) -> dict:
        '''
        Эта функция возвращает сообщение, из которого был удалён указанный тип контента.
        '''
        role = message["role"]
        message_contents = message["content"]
        if not isinstance(message_contents, str):
            message_contents = [i for i in message_contents if i.get("type", None) != content_type]
        return {"role": role, "content": message_contents}

    current_number_of_messages = len(previous_messages)

    if current_number_of_messages > max_amount_of_previous_messages:
        difference = current_number_of_messages - max_amount_of_previous_messages
        previous_messages = previous_messages[difference:]
    
    if current_number_of_messages > store_photos_for_n_messages:
        for i in range(-2, 0):
            idx = -store_photos_for_n_messages - i
            previous_messages[idx] = remove_extra_contents(previous_messages[idx], "input_image")
    
    if current_number_of_messages > store_pdfs_for_n_messages:
        for i in range(-2, 0):
            idx = -store_pdfs_for_n_messages - i
            previous_messages[idx] = remove_extra_contents(previous_messages[idx], "input_file")

    return previous_messages


async def correct_markdown_v2_string(input_string: str) -> str:
    '''
    Корректирует ответ ИИ под стандарт MarkdownV2, чтобы он был совместим с Telegram.
    '''
    def function_for_substitution(input_string: str, pattern: str, symbol_to_remove: str, symbol_to_add: str, replacement_dict: dict[str,str]) -> str:
        '''
        Функция для замены неправильных символов в Markdown markup.
        '''
        extra_symbol_length = len(symbol_to_remove)
        def subs_function(match: re.Match) -> str:
            found_text = match.group()
            text_without_extra_symbols = found_text[extra_symbol_length:-extra_symbol_length]
            for old, new in replacement_dict.items():
                text_without_extra_symbols = text_without_extra_symbols.replace(old, new)
            return f"{symbol_to_add}{text_without_extra_symbols}{symbol_to_add}"
        return re.sub(pattern = pattern, repl = subs_function, string = input_string)

    special_blocks = [] # особые блоки текста, в которые нельзя вносить изменения
    new_string = ""
    inline_code_block = {"pattern": r"(?<!`)`[^`]*?`(?!`)", "flag": re.NOFLAG}
    multiline_code_block = {"pattern": r"```.*?```", "flag": re.S}
    bold_block = {"pattern": r"\*\*[^\*]+\*\*|__[^_]+__", "flag": re.NOFLAG}
    italic_block = {"pattern": r"(?<!\*)\*[^\*]+\*(?!\*)|(?<!_)_[^_]+_(?!_)", "flag": re.NOFLAG}
    block_types = [inline_code_block, multiline_code_block, bold_block, italic_block]

    for block in block_types:
        special_blocks += [i.span() for i in re.finditer(pattern = block["pattern"], string = input_string, flags = block["flag"])]

    replacement_dict = {
        '_': r'\_', '*': r'\*', '[': r'\[', ']': r'\]',
        '(': r'\(', ')': r'\)', '~': r'\~', '`': r'\`',
        '>': r'\>', '#': r'\#', '+': r'\+', '-': r'\-',
        '=': r'\=', '|': r'\|', '{': r'\{', '}': r'\}',
        '.': r'\.', '!': r'\!'
    }

    if special_blocks:
        starting_positions = sorted([index[0] for index in special_blocks])
        ending_positions = sorted([index[1] for index in special_blocks])
        # эффективный поиск по упорядоченному массиву. Не делает замены в особых блоках.
        for pos, symbol in enumerate(input_string):
            if (insertion_pos := bisect_right(starting_positions, pos)) > 0 and pos < ending_positions[insertion_pos-1]:
                new_string += symbol
            else:
                new_string += replacement_dict.get(symbol, symbol)
        # В ответах ИИ формат курсива и жирного текста отличается от Telegram
        new_string = function_for_substitution(new_string, italic_block["pattern"], "_", "_", replacement_dict)
        new_string = function_for_substitution(new_string, bold_block["pattern"], "**", "*", replacement_dict)
    else:
        for old, new in replacement_dict.items():
            input_string = input_string.replace(old, new)
        new_string = input_string

    return new_string

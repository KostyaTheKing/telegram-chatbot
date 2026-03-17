import asyncio
import logging
from sys import stdout

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.handlers import router
from app.database.models import async_main, close_connection
from config import TELE_API_TOKEN


dp = Dispatcher()

async def main() -> None:
    
    TOKEN = TELE_API_TOKEN
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    dp.startup.register(async_main)
    dp.shutdown.register(close_connection)
    
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO, stream=stdout)
    asyncio.run(main())

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from .config import load_config
from .handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()

    session = None
    if config.telegram_api_url:
        session = AiohttpSession(api=TelegramAPIServer.from_base(config.telegram_api_url, is_local=True))

    bot = Bot(config.bot_token, session=session)
    dp = Dispatcher(config=config, semaphore=asyncio.Semaphore(config.max_concurrent_downloads))
    dp.include_router(router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

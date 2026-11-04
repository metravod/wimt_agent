"""Start the bot: `python -m app`."""
import asyncio
import logging
import sys

from aiogram import Dispatcher

from app import bot, config, db, handlers, scheduler


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN or not config.OPENAI_API_KEY:
        sys.exit("BOT_TOKEN and OPENAI_API_KEY must be set, see README.md")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    db.connect(config.DATA_DIR / "bot.db")
    telegram = await bot.start(config.BOT_TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(handlers.router)
    clock = asyncio.create_task(scheduler.run())  # noqa: F841 — keep a reference so it isn't garbage-collected
    logging.info("@%s is running", bot.username)
    await dispatcher.start_polling(telegram)


asyncio.run(main())

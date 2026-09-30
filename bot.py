import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
from services import reminders

from handlers import start, create, lists, actions, settings, reminder_cb


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("bot")

    await database.init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    reminders.set_bot(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start.router)
    dp.include_router(create.router)
    dp.include_router(lists.router)
    dp.include_router(actions.router)
    dp.include_router(settings.router)
    dp.include_router(reminder_cb.router)

    reminders.start()
    await reminders.restore_all()
    await reminders.restore_digests()

    log.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        reminders.shutdown()
        await database.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
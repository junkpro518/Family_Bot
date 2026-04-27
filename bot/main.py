"""نقطة بداية البوت."""

from __future__ import annotations

import asyncio
import logging
import sys

from telegram.ext import ApplicationBuilder

from bot.auth import OwnerStorage
from bot.config import OWNER_FILE, Config
from bot.handlers import register_handlers
from bot.notion import NotionClient
from bot.scheduler import create_scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def run() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    config = Config.load()
    notion = NotionClient(token=config.notion_token, database_id=config.notion_database_id)

    missing = notion.ensure_schema()
    if missing:
        logger.warning("Missing Notion properties: %s", missing)
        try:
            notion.add_missing_properties(missing)
            logger.info("Added missing properties to Notion database.")
        except Exception:
            logger.exception(
                "Could not auto-add properties. Please add them manually in Notion: %s",
                missing,
            )
            sys.exit(1)

    owner_storage = OwnerStorage(OWNER_FILE)

    app = (
        ApplicationBuilder()
        .token(config.telegram_token)
        .build()
    )
    app.bot_data["notion"] = notion
    app.bot_data["owner_storage"] = owner_storage
    app.bot_data["timezone"] = config.timezone

    register_handlers(app)

    scheduler = create_scheduler(
        notion=notion,
        bot=app.bot,
        timezone=config.timezone,
        get_owner_chat_id=owner_storage.get_owner_chat_id,
    )

    async with app:
        await app.initialize()
        scheduler.start()
        logger.info("Scheduler started. Bot starting polling...")
        await app.start()
        await app.updater.start_polling()
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()
            scheduler.shutdown(wait=False)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

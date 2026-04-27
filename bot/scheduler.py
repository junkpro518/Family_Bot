"""جدولة المهام: تذكير ظهراً، إعادة كل ساعة في :45، ريسيت شهري."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot
from telegram.constants import ParseMode

from bot import messages
from bot.distribute import compute_schedule
from bot.handlers import make_confirm_button
from bot.notion import NotionClient, Relative

logger = logging.getLogger(__name__)


def create_scheduler(
    notion: NotionClient,
    bot: Bot,
    timezone: str,
    get_owner_chat_id,
) -> AsyncIOScheduler:
    tz = ZoneInfo(timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    async def daily_noon_job() -> None:
        await _run_daily_noon(notion, bot, tz, get_owner_chat_id)

    async def hourly_45_job() -> None:
        await _run_hourly_45(notion, bot, tz, get_owner_chat_id)

    async def monthly_reset_job() -> None:
        await _run_monthly_reset(notion, bot, tz, get_owner_chat_id)

    scheduler.add_job(
        daily_noon_job,
        CronTrigger(hour=12, minute=0, timezone=tz),
        id="daily_noon",
        replace_existing=True,
    )
    scheduler.add_job(
        hourly_45_job,
        CronTrigger(hour="12-23", minute=45, timezone=tz),
        id="hourly_45",
        replace_existing=True,
    )
    scheduler.add_job(
        monthly_reset_job,
        CronTrigger(day=1, hour=0, minute=0, timezone=tz),
        id="monthly_reset",
        replace_existing=True,
    )

    return scheduler


async def _run_daily_noon(
    notion: NotionClient,
    bot: Bot,
    tz: ZoneInfo,
    get_owner_chat_id,
) -> None:
    """At 12:00 each day: send reminders for today's scheduled relatives."""
    chat_id = get_owner_chat_id()
    if chat_id is None:
        logger.warning("No owner registered; skipping daily noon job.")
        return
    now = datetime.now(tz)
    relatives = await asyncio.to_thread(notion.get_all_relatives)
    logger.info("Daily noon: checking %d relatives for day %d", len(relatives), now.day)
    for rel in relatives:
        if rel.count_done >= rel.count_target:
            continue
        is_scheduled_today = now.day in rel.schedule_days
        is_pending = rel.pending_since is not None
        if not is_scheduled_today and not is_pending:
            continue
        await _send_reminder(notion, bot, chat_id, rel, now)


async def _run_hourly_45(
    notion: NotionClient,
    bot: Bot,
    tz: ZoneInfo,
    get_owner_chat_id,
) -> None:
    """Each hour at :45 (12:45 to 23:45): re-send pending reminders."""
    chat_id = get_owner_chat_id()
    if chat_id is None:
        return
    now = datetime.now(tz)
    relatives = await asyncio.to_thread(notion.get_all_relatives)
    for rel in relatives:
        if rel.count_done >= rel.count_target:
            continue
        if rel.pending_since is None:
            continue
        await _send_reminder(notion, bot, chat_id, rel, now, refresh_only=True)


async def _run_monthly_reset(
    notion: NotionClient,
    bot: Bot,
    tz: ZoneInfo,
    get_owner_chat_id,
) -> None:
    """1st of each month at 00:00: reset done counters and regenerate schedule."""
    now = datetime.now(tz)
    relatives = await asyncio.to_thread(notion.get_all_relatives)
    logger.info("Monthly reset for %d relatives", len(relatives))

    chat_id = get_owner_chat_id()
    warnings: list[str] = []

    for rel in relatives:
        await asyncio.to_thread(notion.set_done_count, rel.page_id, 0)
        await asyncio.to_thread(notion.clear_pending, rel.page_id)

        if rel.count_target <= 0:
            await asyncio.to_thread(notion.update_monthly_schedule, rel.page_id, [])
            continue

        result = compute_schedule(
            allowed_weekdays=rel.allowed_weekdays,
            count=rel.count_target,
            year=now.year,
            month=now.month,
        )
        await asyncio.to_thread(
            notion.update_monthly_schedule, rel.page_id, result.days
        )
        if result.warning == "no_days":
            warnings.append(messages.no_days_warning(rel.name))
        elif result.warning == "count_exceeds_available":
            warnings.append(
                messages.schedule_warning(
                    rel.name, rel.count_target, len(result.days)
                )
            )

    if chat_id is not None:
        try:
            month_name = now.strftime("%B %Y")
            await bot.send_message(
                chat_id=chat_id,
                text=messages.monthly_reset_done(month_name, len(relatives)),
                parse_mode=ParseMode.MARKDOWN,
            )
            for warn in warnings:
                await bot.send_message(chat_id=chat_id, text=warn)
        except Exception:
            logger.exception("Failed to send monthly reset notification")


async def _send_reminder(
    notion: NotionClient,
    bot: Bot,
    chat_id: int,
    rel: Relative,
    now: datetime,
    refresh_only: bool = False,
) -> None:
    """Send (or re-send) a reminder. Sets pending_since if not already set."""
    try:
        if rel.pending_since is None and not refresh_only:
            await asyncio.to_thread(notion.set_pending, rel.page_id, now)
        elif rel.pending_since is None and refresh_only:
            return
        await bot.send_message(
            chat_id=chat_id,
            text=messages.reminder_message(
                rel.name, rel.count_done, rel.count_target
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=make_confirm_button(rel.page_id),
        )
        await asyncio.sleep(0.5)  # avoid rate limits when many relatives
    except Exception:
        logger.exception("Failed to send reminder for %s", rel.name)

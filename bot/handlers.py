"""معالجات أوامر تيليجرام والأزرار."""

from __future__ import annotations

import logging
from datetime import datetime
from functools import wraps
from typing import Any, Awaitable, Callable
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import messages
from bot.auth import OwnerStorage
from bot.messages import WEEKDAY_NAMES_AR
from bot.notion import NotionClient, Relative

logger = logging.getLogger(__name__)

ADD_NAME, ADD_DAYS, ADD_COUNT = range(3)
EDIT_PICK, EDIT_FIELD, EDIT_NAME, EDIT_DAYS, EDIT_COUNT = range(10, 15)
REMOVE_PICK, REMOVE_CONFIRM = range(20, 22)


# Weekday display order (Sunday first to match Saudi convention)
WEEKDAY_DISPLAY_ORDER = [6, 0, 1, 2, 3, 4, 5]


def _make_days_keyboard(selected: set[int]) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for weekday in WEEKDAY_DISPLAY_ORDER:
        prefix = "✅ " if weekday in selected else ""
        row.append(
            InlineKeyboardButton(
                f"{prefix}{WEEKDAY_NAMES_AR[weekday]}",
                callback_data=f"day:{weekday}",
            )
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✔️ تم", callback_data="day:done")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def _make_relatives_keyboard(
    relatives: list[Relative], action_prefix: str
) -> InlineKeyboardMarkup:
    rows = []
    for rel in relatives:
        rows.append(
            [
                InlineKeyboardButton(
                    rel.name, callback_data=f"{action_prefix}:{rel.page_id}"
                )
            ]
        )
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(rows)


def make_confirm_button(page_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ تواصلت معه", callback_data=f"confirm:{page_id}"
                )
            ]
        ]
    )


HandlerFn = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]


def owner_only(handler: HandlerFn) -> HandlerFn:
    """Decorator: reject messages from non-owner chats."""

    @wraps(handler)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> Any:
        owner_storage: OwnerStorage = context.bot_data["owner_storage"]
        chat = update.effective_chat
        if chat is None:
            return None
        if not owner_storage.has_owner():
            if update.message:
                await update.message.reply_text(
                    "ابدأ أولاً بكتابة /start"
                )
            return None
        if not owner_storage.is_owner(chat.id):
            logger.warning("Rejected message from non-owner chat_id=%s", chat.id)
            return None
        return await handler(update, context)

    return wrapper


# ---------- /start ----------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner_storage: OwnerStorage = context.bot_data["owner_storage"]
    chat = update.effective_chat
    if chat is None or update.message is None:
        return
    if not owner_storage.has_owner():
        owner_storage.set_owner_chat_id(chat.id)
        await update.message.reply_text(messages.OWNER_REGISTERED)
        await update.message.reply_text(messages.WELCOME)
        return
    if not owner_storage.is_owner(chat.id):
        await update.message.reply_text(messages.UNAUTHORIZED)
        return
    await update.message.reply_text(messages.WELCOME)


# ---------- /help ----------


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(messages.HELP)


# ---------- /list ----------


@owner_only
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notion: NotionClient = context.bot_data["notion"]
    relatives = notion.get_all_relatives()
    if not relatives:
        if update.message:
            await update.message.reply_text(messages.list_empty())
        return
    parts = [messages.list_header()]
    for rel in relatives:
        days_ar = [WEEKDAY_NAMES_AR[w] for w in WEEKDAY_DISPLAY_ORDER if w in rel.allowed_weekdays]
        parts.append(messages.list_item(rel.name, days_ar, rel.count_done, rel.count_target))
    if update.message:
        await update.message.reply_text(
            "\n".join(parts), parse_mode=ParseMode.MARKDOWN
        )


# ---------- /today ----------


@owner_only
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notion: NotionClient = context.bot_data["notion"]
    timezone: str = context.bot_data["timezone"]
    today = datetime.now(ZoneInfo(timezone)).date()
    relatives = notion.get_all_relatives()
    today_relatives = [
        rel
        for rel in relatives
        if today.day in rel.schedule_days or rel.pending_since is not None
    ]
    if not today_relatives:
        if update.message:
            await update.message.reply_text(messages.today_empty())
        return
    parts = [messages.today_header(today.strftime("%Y-%m-%d"))]
    for rel in today_relatives:
        status = "🔔 معلق" if rel.pending_since else "📅 اليوم"
        parts.append(f"\n{status} *{rel.name}* ({rel.count_done}/{rel.count_target})")
    if update.message:
        await update.message.reply_text(
            "\n".join(parts), parse_mode=ParseMode.MARKDOWN
        )


# ---------- /status ----------


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notion: NotionClient = context.bot_data["notion"]
    relatives = notion.get_all_relatives()
    if not relatives:
        if update.message:
            await update.message.reply_text(messages.status_empty())
        return
    by_day: dict[int, list[str]] = {}
    for rel in relatives:
        for day in rel.schedule_days:
            by_day.setdefault(day, []).append(rel.name)
    if not by_day:
        if update.message:
            await update.message.reply_text(messages.status_empty())
        return
    parts = ["📅 *جدول الشهر:*\n"]
    for day in sorted(by_day.keys()):
        names = "، ".join(by_day[day])
        parts.append(f"\nيوم {day}: {names}")
    if update.message:
        await update.message.reply_text(
            "\n".join(parts), parse_mode=ParseMode.MARKDOWN
        )


# ---------- /add ----------


@owner_only
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["add_days"] = set()
    if update.message:
        await update.message.reply_text(messages.add_ask_name())
    return ADD_NAME


async def add_receive_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None or update.message.text is None:
        return ADD_NAME
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text(messages.add_ask_name())
        return ADD_NAME
    context.user_data["add_name"] = name
    await update.message.reply_text(
        messages.add_ask_days(),
        reply_markup=_make_days_keyboard(set()),
    )
    return ADD_DAYS


async def add_toggle_day(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return ADD_DAYS
    await query.answer()
    parts = query.data.split(":")
    if len(parts) != 2:
        return ADD_DAYS
    payload = parts[1]
    selected: set[int] = context.user_data.get("add_days", set())
    if payload == "done":
        if not selected:
            await query.answer(messages.add_no_days_selected(), show_alert=True)
            return ADD_DAYS
        await query.edit_message_text(messages.add_ask_count())
        return ADD_COUNT
    try:
        weekday = int(payload)
    except ValueError:
        return ADD_DAYS
    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)
    context.user_data["add_days"] = selected
    await query.edit_message_reply_markup(_make_days_keyboard(selected))
    return ADD_DAYS


async def add_receive_count(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None or update.message.text is None:
        return ADD_COUNT
    try:
        count = int(update.message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(messages.add_invalid_count())
        return ADD_COUNT

    name = context.user_data.get("add_name", "")
    days: set[int] = context.user_data.get("add_days", set())
    notion: NotionClient = context.bot_data["notion"]
    notion.add_relative(name=name, allowed_weekdays=days, count_target=count)

    days_ar = [WEEKDAY_NAMES_AR[w] for w in WEEKDAY_DISPLAY_ORDER if w in days]
    await update.message.reply_text(
        messages.add_success(name, days_ar, count),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove(),
    )
    context.user_data.pop("add_name", None)
    context.user_data.pop("add_days", None)
    return ConversationHandler.END


# ---------- /edit ----------


@owner_only
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    notion: NotionClient = context.bot_data["notion"]
    relatives = notion.get_all_relatives()
    if not relatives:
        if update.message:
            await update.message.reply_text(messages.list_empty())
        return ConversationHandler.END
    if update.message:
        await update.message.reply_text(
            messages.edit_pick(),
            reply_markup=_make_relatives_keyboard(relatives, "edit"),
        )
    return EDIT_PICK


async def edit_pick_relative(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return EDIT_PICK
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text(messages.cancelled())
        return ConversationHandler.END
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return EDIT_PICK
    page_id = parts[1]
    context.user_data["edit_page_id"] = page_id

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 الاسم", callback_data="field:name")],
            [InlineKeyboardButton("📅 الأيام", callback_data="field:days")],
            [InlineKeyboardButton("🔢 عدد المرات", callback_data="field:count")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
        ]
    )
    await query.edit_message_text(messages.edit_what(), reply_markup=keyboard)
    return EDIT_FIELD


async def edit_pick_field(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return EDIT_FIELD
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text(messages.cancelled())
        return ConversationHandler.END
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return EDIT_FIELD
    field = parts[1]
    if field == "name":
        await query.edit_message_text("📝 أرسل الاسم الجديد:")
        return EDIT_NAME
    if field == "days":
        notion: NotionClient = context.bot_data["notion"]
        relative = notion.get_relative(context.user_data["edit_page_id"])
        current = relative.allowed_weekdays if relative else set()
        context.user_data["edit_days"] = current
        await query.edit_message_text(
            "📅 اختر الأيام الجديدة:",
            reply_markup=_make_days_keyboard(current),
        )
        return EDIT_DAYS
    if field == "count":
        await query.edit_message_text("🔢 أرسل العدد الجديد:")
        return EDIT_COUNT
    return EDIT_FIELD


async def edit_apply_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None or update.message.text is None:
        return EDIT_NAME
    new_name = update.message.text.strip()
    if not new_name:
        await update.message.reply_text("📝 أرسل الاسم الجديد:")
        return EDIT_NAME
    page_id = context.user_data.get("edit_page_id")
    if not page_id:
        return ConversationHandler.END
    notion: NotionClient = context.bot_data["notion"]
    relative = notion.get_relative(page_id)
    old_name = relative.name if relative else ""
    notion.update_relative_name(page_id, new_name)
    await update.message.reply_text(messages.edit_name_updated(old_name, new_name))
    return ConversationHandler.END


async def edit_toggle_day(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return EDIT_DAYS
    await query.answer()
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return EDIT_DAYS
    payload = parts[1]
    selected: set[int] = context.user_data.get("edit_days", set())
    if payload == "done":
        if not selected:
            await query.answer(messages.add_no_days_selected(), show_alert=True)
            return EDIT_DAYS
        page_id = context.user_data["edit_page_id"]
        notion: NotionClient = context.bot_data["notion"]
        notion.update_relative_days(page_id, selected)
        relative = notion.get_relative(page_id)
        days_ar = [WEEKDAY_NAMES_AR[w] for w in WEEKDAY_DISPLAY_ORDER if w in selected]
        await query.edit_message_text(
            messages.edit_days_updated(relative.name if relative else "", days_ar)
        )
        return ConversationHandler.END
    try:
        weekday = int(payload)
    except ValueError:
        return EDIT_DAYS
    if weekday in selected:
        selected.remove(weekday)
    else:
        selected.add(weekday)
    context.user_data["edit_days"] = selected
    await query.edit_message_reply_markup(_make_days_keyboard(selected))
    return EDIT_DAYS


async def edit_apply_count(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message is None or update.message.text is None:
        return EDIT_COUNT
    try:
        count = int(update.message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(messages.add_invalid_count())
        return EDIT_COUNT
    page_id = context.user_data.get("edit_page_id")
    if not page_id:
        return ConversationHandler.END
    notion: NotionClient = context.bot_data["notion"]
    notion.update_relative_target(page_id, count)
    relative = notion.get_relative(page_id)
    await update.message.reply_text(
        messages.edit_count_updated(relative.name if relative else "", count)
    )
    return ConversationHandler.END


# ---------- /remove ----------


@owner_only
async def remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    notion: NotionClient = context.bot_data["notion"]
    relatives = notion.get_all_relatives()
    if not relatives:
        if update.message:
            await update.message.reply_text(messages.list_empty())
        return ConversationHandler.END
    if update.message:
        await update.message.reply_text(
            messages.remove_pick(),
            reply_markup=_make_relatives_keyboard(relatives, "remove"),
        )
    return REMOVE_PICK


async def remove_pick_relative(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return REMOVE_PICK
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text(messages.cancelled())
        return ConversationHandler.END
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return REMOVE_PICK
    page_id = parts[1]
    context.user_data["remove_page_id"] = page_id

    notion: NotionClient = context.bot_data["notion"]
    relative = notion.get_relative(page_id)
    if relative is None:
        await query.edit_message_text(messages.cancelled())
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ نعم، احذف", callback_data="remove_yes"),
                InlineKeyboardButton("❌ تراجع", callback_data="cancel"),
            ]
        ]
    )
    await query.edit_message_text(
        messages.remove_confirm(relative.name),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
    return REMOVE_CONFIRM


async def remove_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query is None or query.data is None:
        return REMOVE_CONFIRM
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text(messages.cancelled())
        return ConversationHandler.END
    if query.data != "remove_yes":
        return REMOVE_CONFIRM
    page_id = context.user_data.get("remove_page_id")
    if not page_id:
        return ConversationHandler.END
    notion: NotionClient = context.bot_data["notion"]
    relative = notion.get_relative(page_id)
    name = relative.name if relative else ""
    notion.delete_relative(page_id)
    await query.edit_message_text(messages.removed(name))
    return ConversationHandler.END


# ---------- Cancel ----------


async def conversation_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if update.message:
        await update.message.reply_text(
            messages.cancelled(), reply_markup=ReplyKeyboardRemove()
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(messages.cancelled())
    return ConversationHandler.END


# ---------- Confirm reminder button ----------


async def on_confirm_reminder(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    chat = update.effective_chat
    owner_storage: OwnerStorage = context.bot_data["owner_storage"]
    if chat is None or not owner_storage.is_owner(chat.id):
        await query.answer()
        return
    await query.answer()
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        return
    page_id = parts[1]
    notion: NotionClient = context.bot_data["notion"]
    relative = notion.get_relative(page_id)
    if relative is None:
        await query.edit_message_text("⚠️ القريب غير موجود.")
        return
    # Idempotency: if no pending reminder, treat as already confirmed.
    if relative.pending_since is None:
        await query.edit_message_text(
            messages.already_confirmed_message(relative.name),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    new_count = notion.increment_done(page_id)
    notion.clear_pending(page_id)
    await query.edit_message_text(
        messages.confirmed_message(relative.name, new_count, relative.count_target),
        parse_mode=ParseMode.MARKDOWN,
    )


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("status", cmd_status))

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("add", add_start)],
            states={
                ADD_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_name)
                ],
                ADD_DAYS: [CallbackQueryHandler(add_toggle_day, pattern=r"^day:")],
                ADD_COUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, add_receive_count)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", conversation_cancel),
                CallbackQueryHandler(conversation_cancel, pattern=r"^cancel$"),
            ],
        )
    )

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("edit", edit_start)],
            states={
                EDIT_PICK: [CallbackQueryHandler(edit_pick_relative, pattern=r"^edit:")],
                EDIT_FIELD: [
                    CallbackQueryHandler(edit_pick_field, pattern=r"^field:")
                ],
                EDIT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_apply_name)
                ],
                EDIT_DAYS: [CallbackQueryHandler(edit_toggle_day, pattern=r"^day:")],
                EDIT_COUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, edit_apply_count)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", conversation_cancel),
                CallbackQueryHandler(conversation_cancel, pattern=r"^cancel$"),
            ],
        )
    )

    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("remove", remove_start)],
            states={
                REMOVE_PICK: [
                    CallbackQueryHandler(remove_pick_relative, pattern=r"^remove:")
                ],
                REMOVE_CONFIRM: [
                    CallbackQueryHandler(remove_confirm, pattern=r"^remove_yes$"),
                    CallbackQueryHandler(conversation_cancel, pattern=r"^cancel$"),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", conversation_cancel),
                CallbackQueryHandler(conversation_cancel, pattern=r"^cancel$"),
            ],
        )
    )

    app.add_handler(CallbackQueryHandler(on_confirm_reminder, pattern=r"^confirm:"))

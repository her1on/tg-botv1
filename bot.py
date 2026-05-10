import asyncio
import logging
import time
from collections import defaultdict

from telegram import BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database
import pg_listener
import reminders
from config import BOT_TOKEN, DATABASE_URL, OWNER_IDS, SERVICES, TIME_SLOTS, WORKING_DAYS
from handlers.admin import cb_admin_panel, cb_owner_cancel_ask, cb_owner_cancel_confirm, cmd_admin
from handlers.booking import (
    cb_back_date,
    cb_back_main,
    cb_back_name,
    cb_back_service,
    cb_back_time,
    cb_book,
    cb_confirm,
    cb_date,
    cb_name_entered,
    cb_phone_entered,
    cb_service,
    cb_time,
    cmd_book,
)
from handlers.client import cb_cancel_ask, cb_cancel_confirm, cb_menu, cb_my_bookings, cmd_my_bookings, cmd_start
from states import CONFIRM, ENTER_NAME, ENTER_PHONE, SELECT_DATE, SELECT_SERVICE, SELECT_TIME

_fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(_fmt)
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_console)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

_error_counts: dict[str, int] = defaultdict(int)
_ALERT_THRESHOLD = 3


def _validate_env() -> None:
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    if not DATABASE_URL:
        errors.append("DATABASE_URL не задан")
    if not OWNER_IDS:
        errors.append("OWNER_IDS не задан")
    if not SERVICES:
        errors.append("SERVICES пустой")
    if not TIME_SLOTS:
        errors.append("TIME_SLOTS пустой")
    if not WORKING_DAYS:
        errors.append("WORKING_DAYS пустой")
    if errors:
        raise RuntimeError("Ошибки в .env:\n" + "\n".join(f"  - {e}" for e in errors))


def _init_db_with_retry(max_attempts: int = 5) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            database.init_db()
            return
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning(
                "DB init attempt %d/%d failed: %s. Retrying in %ds...",
                attempt, max_attempts, exc, wait,
            )
            if attempt == max_attempts:
                raise
            time.sleep(wait)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_type = type(context.error).__name__
    logger.error("Unhandled exception for update %s:", update, exc_info=context.error)

    _error_counts[error_type] += 1
    if _error_counts[error_type] >= _ALERT_THRESHOLD:
        _error_counts[error_type] = 0
        try:
            for owner_id in OWNER_IDS:
                await context.bot.send_message(
                    chat_id=owner_id,
                    text=f"⚠️ Повторяющаяся ошибка ({error_type}) — {_ALERT_THRESHOLD} раз подряд.\n"
                         "Проверьте логи Railway.",
                )
        except Exception:
            pass


async def _post_init(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("JobQueue not available — reminders will not be sent.")
        return
    try:
        bookings = await asyncio.to_thread(database.get_all_upcoming_bookings)
        count = 0
        for b in bookings:
            reminders.schedule_reminder(app, b.id, b.user_id, b.service, b.date, b.time)
            count += 1
        if count:
            logger.info("Rescheduled %d reminder(s) after restart.", count)
    except Exception:
        logger.exception("Failed to reschedule reminders on startup — bot will still run.")
    app.job_queue.run_repeating(reminders.daily_cleanup, interval=86400, first=3600, name="daily_cleanup")
    app.job_queue.run_repeating(reminders.check_web_bookings, interval=600, first=60, name="check_web_bookings")
    asyncio.create_task(pg_listener.listen_appointments(app), name="pg_listener")
    await app.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("book", "Записаться"),
        BotCommand("mybookings", "Мои записи"),
    ])


async def _post_shutdown(app: Application) -> None:
    database.close_pool()
    logger.warning("Bot shut down.")


def main() -> None:
    _validate_env()
    _init_db_with_retry()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_book, pattern="^book$"),
            CommandHandler("book", cmd_book),
        ],
        states={
            SELECT_SERVICE: [
                CallbackQueryHandler(cb_service, pattern=r"^svc:"),
                CallbackQueryHandler(cb_back_main, pattern="^back:main$"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(cb_date, pattern=r"^date:"),
                CallbackQueryHandler(cb_back_service, pattern="^back:service$"),
            ],
            SELECT_TIME: [
                CallbackQueryHandler(cb_time, pattern=r"^time:"),
                CallbackQueryHandler(cb_time, pattern="^taken$"),
                CallbackQueryHandler(cb_back_date, pattern="^back:date$"),
            ],
            ENTER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cb_name_entered),
                CallbackQueryHandler(cb_back_time, pattern="^back:time$"),
            ],
            ENTER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cb_phone_entered),
                CallbackQueryHandler(cb_back_name, pattern="^back:name$"),
            ],
            CONFIRM: [
                CallbackQueryHandler(cb_confirm, pattern="^confirm$"),
                CallbackQueryHandler(cb_back_main, pattern="^back:main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cb_back_main, pattern="^back:main$"),
            CallbackQueryHandler(cb_menu, pattern="^menu$"),
        ],
        name="booking_conv",
        allow_reentry=True,
    )

    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("mybookings", cmd_my_bookings))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(cb_my_bookings, pattern="^my_bookings$"))
    app.add_handler(CallbackQueryHandler(cb_cancel_ask, pattern=r"^cancel_ask:"))
    app.add_handler(CallbackQueryHandler(cb_cancel_confirm, pattern=r"^cancel_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_admin_panel, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(cb_owner_cancel_ask, pattern=r"^owner_cancel_ask:"))
    app.add_handler(CallbackQueryHandler(cb_owner_cancel_confirm, pattern=r"^owner_cancel:"))
    app.add_handler(CallbackQueryHandler(cb_menu, pattern="^menu$"))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

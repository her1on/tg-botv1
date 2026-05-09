import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import BotCommand
from telegram.ext import Application, ContextTypes

import database
from config import SALON_NAME, TIMEZONE

logger = logging.getLogger(__name__)


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    try:
        await context.bot.send_message(
            chat_id=data["user_id"],
            text=(
                f"⏰ Напоминание!\n\n"
                f"Завтра у вас запись в {SALON_NAME}:\n\n"
                f"Услуга: {data['service']}\n"
                f"Время: {data['time']}"
            ),
        )
    except Exception as exc:
        logger.error("Reminder failed: %s", exc)


def schedule_reminder(
    app: Application, booking_id: int, user_id: int,
    service: str, date_str: str, time_str: str,
) -> None:
    tz = ZoneInfo(TIMEZONE)
    booking_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    reminder_dt = booking_dt - timedelta(hours=24)
    if reminder_dt > datetime.now(tz):
        app.job_queue.run_once(
            send_reminder,
            when=reminder_dt,
            data={"user_id": user_id, "service": service, "date": date_str, "time": time_str},
            name=f"reminder_{booking_id}",
        )


def cancel_reminder(app: Application, booking_id: int) -> None:
    for job in app.job_queue.get_jobs_by_name(f"reminder_{booking_id}"):
        job.schedule_removal()


async def _daily_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = database.cleanup_old_bookings()
    if deleted:
        logger.info("Cleanup: removed %d booking(s) older than 45 days.", deleted)


async def post_init(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("JobQueue not available — reminders will not be sent.")
        return
    bookings = database.get_all_upcoming_bookings()
    count = 0
    for b in bookings:
        schedule_reminder(app, b.id, b.user_id, b.service, b.date, b.time)
        count += 1
    if count:
        logger.info("Rescheduled %d reminder(s) after restart.", count)
    app.job_queue.run_repeating(_daily_cleanup, interval=86400, first=0, name="daily_cleanup")
    await app.bot.set_my_commands([
        BotCommand("start", "Главное меню"),
        BotCommand("book", "Записаться"),
        BotCommand("mybookings", "Мои записи"),
    ])


async def post_shutdown(app: Application) -> None:
    database.close_pool()
    logger.warning("Bot shut down.")

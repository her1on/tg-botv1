import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

import database
from config import OWNER_IDS, SALON_NAME, TIMEZONE
from utils import fmt_date

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


async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = await asyncio.to_thread(database.cleanup_old_bookings)
    if deleted:
        logger.info("Cleanup: removed %d booking(s) older than 45 days.", deleted)


async def check_web_bookings(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify owner about new bookings submitted via the website."""
    try:
        bookings = await asyncio.to_thread(database.get_unnotified_web_bookings)
        for b in bookings:
            date_str = str(b["appointment_date"])
            time_str = str(b["appointment_time"])[:5]
            text = (
                f"🌐 Новая запись с сайта!\n\n"
                f"Имя: {b['name']}\n"
                f"Телефон: {b['phone']}\n"
                f"Услуга: {b['service']}\n"
                f"Дата: {fmt_date(date_str)}\n"
                f"Время: {time_str}"
            )
            if b.get("notes"):
                text += f"\nКомментарий: {b['notes']}"
            for owner_id in OWNER_IDS:
                if not owner_id:
                    continue
                try:
                    await context.bot.send_message(chat_id=owner_id, text=text)
                except Exception as exc:
                    logger.error("Web booking notify failed for %d: %s", owner_id, exc)
            await asyncio.to_thread(database.mark_web_booking_notified, b["id"])
    except Exception as exc:
        logger.error("check_web_bookings failed: %s", exc)

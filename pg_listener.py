import asyncio
import json
import logging
import select

import psycopg2
import psycopg2.extensions

import database
from config import DATABASE_URL, OWNER_IDS
from utils import fmt_date

logger = logging.getLogger(__name__)

_POLL_TIMEOUT = 5.0
_RECONNECT_DELAY = 30.0


async def _dispatch(record: dict, app) -> None:
    date_str = str(record.get("appointment_date", ""))
    time_str = str(record.get("appointment_time", ""))[:5]
    text = (
        f"🌐 Новая запись с сайта!\n\n"
        f"Имя: {record.get('name', '')}\n"
        f"Телефон: {record.get('phone', '')}\n"
        f"Услуга: {record.get('service', '')}\n"
        f"Дата: {fmt_date(date_str)}\n"
        f"Время: {time_str}"
    )
    if record.get("notes"):
        text += f"\nКомментарий: {record['notes']}"

    for owner_id in OWNER_IDS:
        try:
            await app.bot.send_message(chat_id=owner_id, text=text)
        except Exception as exc:
            logger.error("pg_listener: notify owner %d failed: %s", owner_id, exc)

    booking_id = record.get("id")
    if booking_id:
        try:
            await asyncio.to_thread(database.mark_web_booking_notified, booking_id)
        except Exception as exc:
            logger.error("pg_listener: mark_notified failed for %s: %s", booking_id, exc)


def _wait_notify(conn: psycopg2.extensions.connection) -> None:
    select.select([conn], [], [], _POLL_TIMEOUT)


async def listen_appointments(app) -> None:
    """Persistent LISTEN loop on 'new_appointment' channel; auto-reconnects on failure."""
    while True:
        conn = None
        try:
            conn = await asyncio.to_thread(psycopg2.connect, DATABASE_URL)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute("LISTEN new_appointment;")
            logger.info("pg_listener: connected and listening.")

            while True:
                await asyncio.to_thread(_wait_notify, conn)
                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    try:
                        record = json.loads(notify.payload)
                        asyncio.create_task(_dispatch(record, app))
                    except Exception as exc:
                        logger.error("pg_listener: bad payload: %s", exc)

        except asyncio.CancelledError:
            logger.info("pg_listener: cancelled.")
            raise
        except Exception as exc:
            logger.error("pg_listener: %s — reconnect in %.0fs.", exc, _RECONNECT_DELAY)
        finally:
            if conn is not None:
                try:
                    await asyncio.to_thread(conn.close)
                except Exception:
                    pass

        await asyncio.sleep(_RECONNECT_DELAY)

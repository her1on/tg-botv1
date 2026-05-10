import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TypedDict

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from config import DATABASE_URL
from models import Booking

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


class AppointmentRow(TypedDict):
    id: str
    name: str
    phone: str
    service: str
    appointment_date: object
    appointment_time: object
    notes: str | None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    1, 10, DATABASE_URL,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=5,
                    keepalives_count=3,
                )
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


@contextmanager
def _conn():
    pool = _get_pool()
    try:
        conn = pool.getconn()
    except psycopg2.pool.PoolError:
        logger.error("Database connection pool exhausted")
        raise
    close_on_return = False
    try:
        yield conn
        conn.commit()
    except psycopg2.OperationalError:
        close_on_return = True
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=close_on_return)


def init_db() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id         SERIAL PRIMARY KEY,
                    user_id    BIGINT  NOT NULL,
                    username   TEXT    NOT NULL DEFAULT '',
                    full_name  TEXT    NOT NULL DEFAULT '',
                    phone      TEXT    NOT NULL DEFAULT '',
                    service    TEXT    NOT NULL,
                    date       DATE    NOT NULL,
                    time       TEXT    NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    UNIQUE(date, time)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name             TEXT        NOT NULL DEFAULT '',
                    phone            TEXT        NOT NULL DEFAULT '',
                    service          TEXT        NOT NULL DEFAULT '',
                    appointment_date DATE        NOT NULL,
                    appointment_time TIME        NOT NULL,
                    notes            TEXT,
                    source           TEXT        NOT NULL DEFAULT 'web',
                    owner_notified   BOOLEAN     NOT NULL DEFAULT false,
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)


def _row_to_booking(row) -> Booking:
    return Booking(
        id=row["id"],
        user_id=row["user_id"],
        service=row["service"],
        date=str(row["date"]),
        time=row["time"],
        full_name=row["full_name"],
        username=row["username"],
        phone=row["phone"],
    )


def add_booking(
    user_id: int, username: str, full_name: str, phone: str,
    service: str, date: str, time: str,
) -> int | None:
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO bookings
                       (user_id, username, full_name, phone, service, date, time, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (user_id, username, full_name, phone, service, date, time,
                     datetime.now(timezone.utc)),
                )
                return cur.fetchone()["id"]
    except psycopg2.IntegrityError:
        return None


def get_user_bookings(user_id: int) -> list[Booking]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, user_id, service, date, time, full_name, username, phone
                   FROM bookings WHERE user_id = %s AND date >= CURRENT_DATE
                   ORDER BY date, time""",
                (user_id,),
            )
            return [_row_to_booking(r) for r in cur.fetchall()]


def get_all_upcoming_bookings() -> list[Booking]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, user_id, service, date, time, full_name, username, phone
                   FROM bookings WHERE date >= CURRENT_DATE ORDER BY date, time"""
            )
            return [_row_to_booking(r) for r in cur.fetchall()]


def get_booking_by_id(booking_id: int, user_id: int | None = None) -> Booking | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id is not None:
                cur.execute(
                    """SELECT id, user_id, service, date, time, full_name, username, phone
                       FROM bookings WHERE id = %s AND user_id = %s""",
                    (booking_id, user_id),
                )
            else:
                cur.execute(
                    """SELECT id, user_id, service, date, time, full_name, username, phone
                       FROM bookings WHERE id = %s""",
                    (booking_id,),
                )
            row = cur.fetchone()
            return _row_to_booking(row) if row else None


def cancel_booking(booking_id: int, user_id: int | None = None) -> Booking | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id is not None:
                cur.execute(
                    """DELETE FROM bookings WHERE id = %s AND user_id = %s
                       RETURNING id, user_id, service, date, time, full_name, username, phone""",
                    (booking_id, user_id),
                )
            else:
                cur.execute(
                    """DELETE FROM bookings WHERE id = %s
                       RETURNING id, user_id, service, date, time, full_name, username, phone""",
                    (booking_id,),
                )
            row = cur.fetchone()
            return _row_to_booking(row) if row else None


def get_appointment_by_id(appointment_id: str) -> AppointmentRow | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, name, phone, service,
                          appointment_date, appointment_time, notes
                   FROM appointments WHERE id = %s""",
                (appointment_id,),
            )
            return cur.fetchone()


def cancel_appointment(appointment_id: str) -> AppointmentRow | None:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """DELETE FROM appointments WHERE id = %s
                   RETURNING id, name, phone, service,
                             appointment_date, appointment_time, notes""",
                (appointment_id,),
            )
            return cur.fetchone()


def get_all_upcoming_appointments() -> list[AppointmentRow]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, phone, service,
                       appointment_date, appointment_time, notes
                FROM appointments
                WHERE appointment_date >= CURRENT_DATE
                ORDER BY appointment_date, appointment_time
            """)
            return cur.fetchall()


def get_unnotified_web_bookings() -> list[AppointmentRow]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, phone, service,
                       appointment_date, appointment_time, notes
                FROM appointments
                WHERE owner_notified = false
                  AND appointment_date >= CURRENT_DATE
                ORDER BY created_at
            """)
            return cur.fetchall()


def mark_web_booking_notified(booking_id: str) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE appointments SET owner_notified = true WHERE id = %s",
                (booking_id,),
            )


def get_booked_times(date: str) -> list[str]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT time FROM bookings WHERE date = %s
                UNION
                SELECT appointment_time::text FROM appointments WHERE appointment_date = %s
            """, (date, date))
            return [r["time"][:5] for r in cur.fetchall()]


def cleanup_old_bookings() -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bookings WHERE date < CURRENT_DATE - INTERVAL '45 days'")
            deleted = cur.rowcount
            cur.execute("DELETE FROM appointments WHERE appointment_date < CURRENT_DATE - INTERVAL '45 days'")
            deleted += cur.rowcount
            return deleted

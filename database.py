import os
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
import psycopg2.pool

from models import Booking

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DATABASE_URL)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def _conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


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


def _row_to_booking(row: tuple) -> Booking:
    return Booking(
        id=row[0], user_id=row[1], service=row[2],
        date=str(row[3]), time=row[4], full_name=row[5],
        username=row[6], phone=row[7],
    )


def add_booking(
    user_id: int, username: str, full_name: str, phone: str,
    service: str, date: str, time: str,
) -> int | None:
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO bookings
                       (user_id, username, full_name, phone, service, date, time, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                    (user_id, username, full_name, phone, service, date, time,
                     datetime.now(timezone.utc)),
                )
                return cur.fetchone()[0]
    except psycopg2.IntegrityError:
        return None


def get_user_bookings(user_id: int) -> list[Booking]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, service, date, time, full_name, username, phone
                   FROM bookings WHERE user_id = %s AND date >= CURRENT_DATE
                   ORDER BY date, time""",
                (user_id,),
            )
            return [_row_to_booking(r) for r in cur.fetchall()]


def get_all_upcoming_bookings() -> list[Booking]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, service, date, time, full_name, username, phone
                   FROM bookings WHERE date >= CURRENT_DATE ORDER BY date, time"""
            )
            return [_row_to_booking(r) for r in cur.fetchall()]


def get_booking_by_id(booking_id: int) -> Booking | None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, user_id, service, date, time, full_name, username, phone
                   FROM bookings WHERE id = %s""",
                (booking_id,),
            )
            row = cur.fetchone()
            return _row_to_booking(row) if row else None


def cancel_booking(booking_id: int, user_id: int | None = None) -> Booking | None:
    with _conn() as conn:
        with conn.cursor() as cur:
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


def get_booked_times(date: str) -> list[str]:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT time FROM bookings WHERE date = %s", (date,))
            return [r[0] for r in cur.fetchall()]


def cleanup_old_bookings() -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bookings WHERE date < CURRENT_DATE - INTERVAL '45 days'")
            return cur.rowcount

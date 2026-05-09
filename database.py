import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bookings.db")


def init_db() -> None:
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                username    TEXT,
                full_name   TEXT,
                phone       TEXT,
                service     TEXT NOT NULL,
                date        TEXT NOT NULL,
                time        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                UNIQUE(date, time)
            )
        """)
        # Migration: add phone column to existing databases
        try:
            conn.execute("ALTER TABLE bookings ADD COLUMN phone TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def add_booking(
    user_id: int,
    username: str,
    full_name: str,
    phone: str,
    service: str,
    date: str,
    time: str,
) -> int | None:
    """Insert a booking. Returns new row id, or None if the slot is taken."""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cur = conn.execute(
                """
                INSERT INTO bookings (user_id, username, full_name, phone, service, date, time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, username, full_name, phone, service, date, time, datetime.now().isoformat()),
            )
            conn.commit()
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_bookings(user_id: int) -> list[tuple]:
    """Return upcoming bookings for this user."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute(
            """
            SELECT id, service, date, time FROM bookings
            WHERE user_id = ? AND date >= date('now')
            ORDER BY date, time
            """,
            (user_id,),
        )
        return cur.fetchall()


def get_all_upcoming_bookings() -> list[tuple]:
    """Return all upcoming bookings for the owner."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute(
            """
            SELECT id, full_name, username, phone, service, date, time FROM bookings
            WHERE date >= date('now')
            ORDER BY date, time
            """
        )
        return cur.fetchall()


def get_booking_by_id(booking_id: int) -> tuple | None:
    """Return a single booking row: (id, user_id, service, date, time, full_name, username, phone)."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute(
            "SELECT id, user_id, service, date, time, full_name, username, phone FROM bookings WHERE id = ?",
            (booking_id,),
        )
        return cur.fetchone()


def cancel_booking(booking_id: int, user_id: int | None = None) -> tuple | None:
    """Delete a booking and return its data. Pass user_id to verify ownership."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        if user_id is not None:
            cur = conn.execute(
                "SELECT id, user_id, service, date, time, full_name, username, phone FROM bookings WHERE id = ? AND user_id = ?",
                (booking_id, user_id),
            )
        else:
            cur = conn.execute(
                "SELECT id, user_id, service, date, time, full_name, username, phone FROM bookings WHERE id = ?",
                (booking_id,),
            )
        booking = cur.fetchone()
        if not booking:
            return None
        conn.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        conn.commit()
        return booking


def get_all_for_reminder_reschedule() -> list[tuple]:
    """Return (id, user_id, service, date, time) for all upcoming bookings."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute(
            "SELECT id, user_id, service, date, time FROM bookings WHERE date >= date('now') ORDER BY date, time"
        )
        return cur.fetchall()


def cleanup_old_bookings() -> int:
    """Delete bookings older than 45 days. Returns number of deleted rows."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute("DELETE FROM bookings WHERE date < date('now', '-45 days')")
        conn.commit()
        return cur.rowcount


def get_booked_times(date: str) -> list[str]:
    """Return all taken time slots for a given date."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        cur = conn.execute("SELECT time FROM bookings WHERE date = ?", (date,))
        return [row[0] for row in cur.fetchall()]

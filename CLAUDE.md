# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

There are no test commands or build steps — this is a single-process Python application.

## Architecture

A Telegram bot for beauty salon appointment booking. Deployed on Railway, uses Supabase (PostgreSQL) as the database.

### Module structure

- [bot.py](bot.py) — Entry point: registers handlers, builds `Application`, calls `main()`
- [config.py](config.py) — Loads and validates environment variables from `.env`
- [database.py](database.py) — PostgreSQL via `psycopg2` (`ThreadedConnectionPool`); all DB operations
- [models.py](models.py) — `Booking` dataclass
- [keyboards.py](keyboards.py) — All `InlineKeyboardMarkup` builders
- [utils.py](utils.py) — `fmt_date`, `is_valid_phone`, `notify_owner`
- [reminders.py](reminders.py) — JobQueue reminder scheduling, `post_init`, `post_shutdown`
- [handlers/booking.py](handlers/booking.py) — Booking `ConversationHandler` states and callbacks
- [handlers/client.py](handlers/client.py) — `/start`, my bookings, client-side cancellation
- [handlers/admin.py](handlers/admin.py) — `/admin` panel, owner-side cancellation

### Booking Conversation Flow

`ConversationHandler` states: `SELECT_SERVICE → SELECT_DATE → SELECT_TIME → ENTER_NAME → ENTER_PHONE → CONFIRM`.

After confirmation, `schedule_reminder()` registers a JobQueue reminder 24 hours before the appointment. On restart, `post_init()` re-registers all upcoming reminders from the database via `get_all_upcoming_bookings()`.

### Double-booking Prevention

A `UNIQUE(date, time)` constraint on the bookings table is the authoritative guard against race conditions. `add_booking()` catches `IntegrityError` and returns `None` on collision.

### Admin Panel

Triggered by `/admin` (text) or the "Панель владельца" button (callback). Access is gated by `OWNER_IDS`. The panel shows up to 40 upcoming bookings with per-booking cancel buttons; `/admin` command sends the full list as plain text (split across messages if > 4000 chars). Owner receives a DM on every new booking or cancellation via `notify_owner()`.

### Cancellation

`cancel_booking()` uses an atomic `DELETE ... RETURNING` — no separate SELECT + DELETE.

## Environment Variables

Required in `.env` (see [.env.example](.env.example)):

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `DATABASE_URL` | PostgreSQL connection URL (Supabase pooler, Session mode port 5432) |
| `OWNER_IDS` | Comma-separated Telegram user IDs of owners (e.g. `123456,789012`) |
| `SALON_NAME` | Display name shown in messages |
| `TIMEZONE` | Timezone string (e.g. `Europe/Moscow`) |
| `WORKING_DAYS` | Comma-separated weekday indices 0–6 (0=Mon) |
| `SERVICES` | Comma-separated list of available services |
| `TIME_SLOTS` | Comma-separated available times (HH:MM) |

`OWNER_ID` (singular) is also accepted as a fallback for backwards compatibility.

`.env` and `bot.log` are gitignored.

## Deployment

- Platform: Railway (region: Europe West)
- Database: Supabase PostgreSQL via Session Mode pooler (`aws-0-eu-west-1.pooler.supabase.com:5432`)
- Railway does not support IPv6 — use the pooler URL, not the direct Supabase connection string
- Pooler username format: `postgres.<project-ref>`

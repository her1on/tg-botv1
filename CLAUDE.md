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

A Telegram bot for beauty salon appointment booking. Three core modules:

- [bot.py](bot.py) — All bot logic: handlers, conversation flow, reminders, admin panel (~656 lines)
- [database.py](database.py) — SQLite operations (bookings table: `id, user_id, username, full_name, phone, service, date, time, created_at`)
- [config.py](config.py) — Loads and validates environment variables from `.env`

### Booking Conversation Flow

Uses `python-telegram-bot`'s `ConversationHandler` with states: `SELECT_SERVICE → SELECT_DATE → SELECT_TIME → ENTER_PHONE → CONFIRM`. Each step is a callback (`cb_service`, `cb_date`, `cb_time`, `cb_phone_entered`, `cb_confirm`). After confirmation, `schedule_reminder()` registers a JobQueue reminder 24 hours before the appointment.

On restart, `post_init()` re-registers all upcoming reminders from the database.

### State Persistence

`PicklePersistence` saves conversation state across restarts (files: `bot_persistence.*`). The startup code in `main()` handles corrupted persistence files by deleting and recreating them.

### Double-booking Prevention

A `UNIQUE(date, time)` constraint on the bookings table is the authoritative guard against race conditions — not application-level checks.

### Admin Panel

Triggered by `/admin`. Only accessible if `update.effective_user.id == OWNER_ID`. Owner also receives a DM on every new booking or cancellation.

## Environment Variables

Required in `.env` (see [.env.example](.env.example)):

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram bot token from BotFather |
| `OWNER_ID` | Telegram user ID of salon owner (integer) |
| `SALON_NAME` | Display name shown in messages |
| `TIMEZONE` | Timezone string (e.g. `Europe/Moscow`) |
| `WORKING_DAYS` | Comma-separated weekday indices 0–6 (0=Mon) |
| `SERVICES` | Comma-separated list of available services |
| `TIME_SLOTS` | Comma-separated available times (HH:MM) |

`.env`, `*.db`, `bot_persistence*`, and `bot.log` are all gitignored.

import logging
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

import database
from config import BOT_TOKEN, OWNER_ID, SALON_NAME, TIMEZONE, SERVICES, TIME_SLOTS, WORKING_DAYS

_fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(_fmt)
_file = RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
_file.setLevel(logging.WARNING)
_file.setFormatter(_fmt)
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_console)
logging.root.addHandler(_file)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

SELECT_SERVICE, SELECT_DATE, SELECT_TIME, ENTER_PHONE, CONFIRM = range(5)


# ─── Keyboards ────────────────────────────────────────────────────────────────

def main_menu_kb(user_id: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
    ]
    if user_id == OWNER_ID:
        rows.append([InlineKeyboardButton("🔧 Панель владельца", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def services_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(SERVICES), 2):
        row = [InlineKeyboardButton(SERVICES[i], callback_data=f"svc:{SERVICES[i]}")]
        if i + 1 < len(SERVICES):
            row.append(InlineKeyboardButton(SERVICES[i + 1], callback_data=f"svc:{SERVICES[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("← Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(rows)


def dates_kb() -> InlineKeyboardMarkup:
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    rows, row, count, offset = [], [], 0, 1
    while count < 14 and offset <= 90:
        d = today + timedelta(days=offset)
        offset += 1
        if d.weekday() not in WORKING_DAYS:
            continue
        label = f"{d.strftime('%d.%m')} {day_names[d.weekday()]}"
        row.append(InlineKeyboardButton(label, callback_data=f"date:{d.isoformat()}"))
        count += 1
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("← Назад", callback_data="back:service")])
    return InlineKeyboardMarkup(rows)


def times_kb(date_str: str) -> InlineKeyboardMarkup:
    booked = set(database.get_booked_times(date_str))
    rows, row = [], []
    for slot in TIME_SLOTS:
        if slot in booked:
            btn = InlineKeyboardButton(f"❌ {slot}", callback_data="taken")
        else:
            btn = InlineKeyboardButton(f"✅ {slot}", callback_data=f"time:{slot}")
        row.append(btn)
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("← Назад", callback_data="back:date")])
    return InlineKeyboardMarkup(rows)


def phone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back:time")]])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="back:main"),
    ]])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Главное меню", callback_data="menu")]])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")


async def notify_owner(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    if not OWNER_ID:
        return
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=text)
    except Exception as exc:
        logger.error("Owner notification failed: %s", exc)


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
    app: Application, booking_id: int, user_id: int, service: str, date_str: str, time_str: str
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


# ─── Commands ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Добро пожаловать в {SALON_NAME} ✂️💅\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(user.id),
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("У вас нет доступа.")
        return
    bookings = database.get_all_upcoming_bookings()
    if not bookings:
        await update.message.reply_text("Предстоящих записей нет.")
        return
    current_date = None
    lines = []
    for _, full_name, username, phone, service, date_str, time_str in bookings:
        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n📅 {fmt_date(date_str)}")
        uname = f"@{username}" if username else full_name
        lines.append(f"  {time_str} — {service} | {uname} {phone}")
    await update.message.reply_text("Все предстоящие записи:" + "\n".join(lines))


# ─── Booking conversation ─────────────────────────────────────────────────────

async def cb_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выберите услугу:", reply_markup=services_kb())
    return SELECT_SERVICE


async def cb_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service = query.data.split(":", 1)[1]
    context.user_data["service"] = service
    await query.edit_message_text(f"Услуга: {service}\n\nВыберите дату:", reply_markup=dates_kb())
    return SELECT_DATE


async def cb_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":", 1)[1]
    context.user_data["date"] = date_str
    await query.edit_message_text(
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {fmt_date(date_str)}\n\n"
        "Выберите время:",
        reply_markup=times_kb(date_str),
    )
    return SELECT_TIME


async def cb_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query.data == "taken":
        await query.answer("Это время уже занято!", show_alert=True)
        return SELECT_TIME
    await query.answer()
    time_str = query.data.split(":", 1)[1]
    context.user_data["time"] = time_str
    msg = await query.edit_message_text(
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {fmt_date(context.user_data['date'])}\n"
        f"Время: {time_str}\n\n"
        "Введите ваш номер телефона:",
        reply_markup=phone_kb(),
    )
    context.user_data["phone_msg_id"] = msg.message_id
    return ENTER_PHONE


async def cb_phone_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    if sum(c.isdigit() for c in phone) < 7:
        await update.message.reply_text("Введите корректный номер телефона (минимум 7 цифр).")
        return ENTER_PHONE
    context.user_data["phone"] = phone
    text = (
        "Подтвердите запись:\n\n"
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {fmt_date(context.user_data['date'])}\n"
        f"Время: {context.user_data['time']}\n"
        f"Телефон: {phone}"
    )
    phone_msg_id = context.user_data.get("phone_msg_id")
    if phone_msg_id:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=phone_msg_id,
            text=text,
            reply_markup=confirm_kb(),
        )
    else:
        await update.message.reply_text(text, reply_markup=confirm_kb())
    return CONFIRM


async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ud = context.user_data
    service, date_str, time_str, phone = ud["service"], ud["date"], ud["time"], ud["phone"]

    booking_id = database.add_booking(
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name,
        phone=phone,
        service=service,
        date=date_str,
        time=time_str,
    )

    if booking_id is None:
        await query.edit_message_text(
            "Это время только что заняли. Пожалуйста, выберите другое.",
            reply_markup=main_menu_kb(user.id),
        )
        context.user_data.clear()
        return ConversationHandler.END

    await query.edit_message_text(
        f"Запись подтверждена! 🎉\n\n"
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str)}\n"
        f"Время: {time_str}\n\n"
        f"Ждём вас в {SALON_NAME}! 💖",
        reply_markup=main_menu_kb(user.id),
    )

    schedule_reminder(context.application, booking_id, user.id, service, date_str, time_str)

    uname = f"@{user.username}" if user.username else "нет username"
    await notify_owner(
        context,
        f"🆕 Новая запись!\n\n"
        f"Клиент: {user.full_name} ({uname})\n"
        f"Телефон: {phone}\n"
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str)}\n"
        f"Время: {time_str}",
    )

    context.user_data.clear()
    return ConversationHandler.END


# ─── Back navigation ──────────────────────────────────────────────────────────

async def cb_back_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Выберите действие:", reply_markup=main_menu_kb(update.effective_user.id))
    return ConversationHandler.END


async def cb_back_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выберите услугу:", reply_markup=services_kb())
    return SELECT_SERVICE


async def cb_back_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service = context.user_data.get("service", "")
    await query.edit_message_text(f"Услуга: {service}\n\nВыберите дату:", reply_markup=dates_kb())
    return SELECT_DATE


async def cb_back_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_str = context.user_data.get("date", "")
    service = context.user_data.get("service", "")
    await query.edit_message_text(
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str)}\n\n"
        "Выберите время:",
        reply_markup=times_kb(date_str),
    )
    return SELECT_TIME


# ─── Client: my bookings & cancellation ──────────────────────────────────────

async def cb_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bookings = database.get_user_bookings(update.effective_user.id)
    if not bookings:
        await query.edit_message_text("У вас нет предстоящих записей.", reply_markup=back_to_menu_kb())
        return
    lines = ["Ваши предстоящие записи:\n"]
    keyboard = []
    for bid, service, date_str, time_str in bookings:
        lines.append(f"📌 {fmt_date(date_str)} в {time_str} — {service}")
        keyboard.append([InlineKeyboardButton(
            f"❌ Отменить {fmt_date(date_str)} {time_str}",
            callback_data=f"cancel_ask:{bid}",
        )])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="menu")])
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split(":")[1])
    booking = database.get_booking_by_id(booking_id)
    if not booking or booking[1] != update.effective_user.id:
        await query.answer("Запись не найдена.", show_alert=True)
        return
    _, _, service, date_str, time_str, *_ = booking
    await query.edit_message_text(
        f"Вы уверены, что хотите отменить запись?\n\n"
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str)}\n"
        f"Время: {time_str}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Да, отменить", callback_data=f"cancel_confirm:{booking_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="my_bookings"),
        ]]),
    )


async def cb_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    booking_id = int(query.data.split(":")[1])
    user = update.effective_user
    booking = database.cancel_booking(booking_id, user_id=user.id)
    if booking:
        _, _, service, date_str, time_str, *_ = booking
        await query.edit_message_text(
            f"Запись отменена.\n\n"
            f"Услуга: {service}\n"
            f"Дата: {fmt_date(date_str)}\n"
            f"Время: {time_str}",
            reply_markup=main_menu_kb(user.id),
        )
        cancel_reminder(context.application, booking_id)
        uname = f"@{user.username}" if user.username else user.full_name
        await notify_owner(
            context,
            f"❌ Отмена записи!\n\nКлиент: {uname}\nУслуга: {service}\nДата: {fmt_date(date_str)}\nВремя: {time_str}",
        )
    else:
        await query.edit_message_text("Не удалось отменить запись.", reply_markup=main_menu_kb(user.id))


# ─── Owner: admin panel & cancellation ───────────────────────────────────────

async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bookings = database.get_all_upcoming_bookings()
    if not bookings:
        await query.edit_message_text("Предстоящих записей нет.", reply_markup=back_to_menu_kb())
        return
    current_date = None
    lines = []
    keyboard = []
    for bid, full_name, username, phone, service, date_str, time_str in bookings:
        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n📅 {fmt_date(date_str)}")
        uname = f"@{username}" if username else full_name
        lines.append(f"  {time_str} — {service}\n  👤 {uname}  📞 {phone}")
        keyboard.append([InlineKeyboardButton(
            f"❌ {fmt_date(date_str)} {time_str} — {service}",
            callback_data=f"owner_cancel_ask:{bid}",
        )])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="menu")])
    await query.edit_message_text(
        "Все предстоящие записи:" + "".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cb_owner_cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != OWNER_ID:
        await query.answer("Нет доступа.", show_alert=True)
        return
    booking_id = int(query.data.split(":")[1])
    booking = database.get_booking_by_id(booking_id)
    if not booking:
        await query.answer("Запись не найдена.", show_alert=True)
        return
    _, _, service, date_str, time_str, full_name, username, phone = booking
    uname = f"@{username}" if username else full_name
    await query.edit_message_text(
        f"Отменить запись?\n\n"
        f"Клиент: {uname}\n"
        f"Телефон: {phone}\n"
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str)}\n"
        f"Время: {time_str}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Да, отменить", callback_data=f"owner_cancel:{booking_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="admin"),
        ]]),
    )


async def cb_owner_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != OWNER_ID:
        await query.answer("Нет доступа.", show_alert=True)
        return
    booking_id = int(query.data.split(":")[1])
    booking = database.cancel_booking(booking_id)
    if booking:
        _, client_user_id, service, date_str, time_str, full_name, username, phone = booking
        await query.edit_message_text(
            f"Запись отменена.\n\nУслуга: {service}\nДата: {fmt_date(date_str)}\nВремя: {time_str}",
            reply_markup=back_to_menu_kb(),
        )
        cancel_reminder(context.application, booking_id)
        try:
            await context.bot.send_message(
                chat_id=client_user_id,
                text=(
                    f"❌ Ваша запись была отменена администратором.\n\n"
                    f"Услуга: {service}\n"
                    f"Дата: {fmt_date(date_str)}\n"
                    f"Время: {time_str}\n\n"
                    "Пожалуйста, свяжитесь с нами для уточнения деталей."
                ),
            )
        except Exception as exc:
            logger.error("Failed to notify client about cancellation: %s", exc)
    else:
        await query.edit_message_text("Не удалось отменить запись.", reply_markup=back_to_menu_kb())


async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Выберите действие:", reply_markup=main_menu_kb(update.effective_user.id))
    return ConversationHandler.END


# ─── Reliability hooks ────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log every unhandled exception so nothing fails silently."""
    logger.error("Unhandled exception for update %s:", update, exc_info=context.error)


async def _daily_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = database.cleanup_old_bookings()
    if deleted:
        logger.info("Cleanup: removed %d booking(s) older than 45 days.", deleted)


async def post_init(app: Application) -> None:
    """On restart, reschedule reminders for all bookings still in the future."""
    if app.job_queue is None:
        logger.warning("JobQueue not available — reminders will not be sent.")
        return
    bookings = database.get_all_for_reminder_reschedule()
    count = 0
    for booking_id, user_id, service, date_str, time_str in bookings:
        schedule_reminder(app, booking_id, user_id, service, date_str, time_str)
        count += 1
    if count:
        logger.info("Rescheduled %d reminder(s) after restart.", count)
    app.job_queue.run_repeating(_daily_cleanup, interval=86400, first=0, name="daily_cleanup")


async def post_shutdown(app: Application) -> None:
    logger.warning("Bot shut down.")


# ─── Main ─────────────────────────────────────────────────────────────────────

def _validate_env() -> None:
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN не задан")
    if not OWNER_ID:
        errors.append("OWNER_ID не задан")
    if not SERVICES:
        errors.append("SERVICES пустой")
    if not TIME_SLOTS:
        errors.append("TIME_SLOTS пустой")
    if not WORKING_DAYS:
        errors.append("WORKING_DAYS пустой")
    if errors:
        raise RuntimeError("Ошибки в .env:\n" + "\n".join(f"  - {e}" for e in errors))


def _load_persistence() -> PicklePersistence:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_persistence")
    try:
        p = PicklePersistence(filepath=path)
        return p
    except Exception as exc:
        logger.warning("Файл персистентности повреждён, сбрасываю: %s", exc)
        for suffix in ("", ".chat_data", ".user_data", ".bot_data", ".callback_data", ".conversations"):
            try:
                os.remove(path + suffix)
            except FileNotFoundError:
                pass
        return PicklePersistence(filepath=path)


def main() -> None:
    _validate_env()

    database.init_db()

    persistence = _load_persistence()
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    # SIGTERM is handled by PTB's run_polling via signal.signal() on all platforms.

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_book, pattern="^book$")],
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
            ENTER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cb_phone_entered),
                CallbackQueryHandler(cb_back_time, pattern="^back:time$"),
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
        persistent=True,
        allow_reentry=True,
    )

    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
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

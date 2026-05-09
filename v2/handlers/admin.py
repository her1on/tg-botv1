import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import database
from config import OWNER_IDS
from keyboards import back_to_menu_kb
from reminders import cancel_reminder
from utils import fmt_date

logger = logging.getLogger(__name__)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("У вас нет доступа.")
        return
    bookings = database.get_all_upcoming_bookings()
    if not bookings:
        await update.message.reply_text("Предстоящих записей нет.")
        return
    current_date = None
    lines = []
    for b in bookings:
        if b.date != current_date:
            current_date = b.date
            lines.append(f"\n📅 {fmt_date(b.date)}")
        uname = f"{b.full_name} (@{b.username})" if b.username and b.full_name else b.full_name or f"@{b.username}"
        lines.append(f"  {b.time} — {b.service} | {uname} {b.phone}")
    await update.message.reply_text("Все предстоящие записи:" + "\n".join(lines))


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
    for b in bookings:
        if b.date != current_date:
            current_date = b.date
            lines.append(f"\n📅 {fmt_date(b.date)}")
        uname = f"{b.full_name} (@{b.username})" if b.username and b.full_name else b.full_name or f"@{b.username}"
        lines.append(f"  {b.time} — {b.service}\n  👤 {uname}  📞 {b.phone}")
        keyboard.append([InlineKeyboardButton(
            f"❌ {fmt_date(b.date)} {b.time} — {b.service}",
            callback_data=f"owner_cancel_ask:{b.id}",
        )])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="menu")])
    await query.edit_message_text(
        "Все предстоящие записи:\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cb_owner_cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    booking_id = int(query.data.split(":")[1])
    booking = database.get_booking_by_id(booking_id)
    if not booking:
        await query.answer("Запись не найдена.", show_alert=True)
        return
    uname = f"@{booking.username}" if booking.username else booking.full_name
    await query.edit_message_text(
        f"Отменить запись?\n\n"
        f"Клиент: {uname}\n"
        f"Телефон: {booking.phone}\n"
        f"Услуга: {booking.service}\n"
        f"Дата: {fmt_date(booking.date)}\n"
        f"Время: {booking.time}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Да, отменить", callback_data=f"owner_cancel:{booking_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="admin"),
        ]]),
    )


async def cb_owner_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    booking_id = int(query.data.split(":")[1])
    booking = database.cancel_booking(booking_id)
    if not booking:
        await query.edit_message_text("Не удалось отменить запись.", reply_markup=back_to_menu_kb())
        return
    await query.edit_message_text(
        f"Запись отменена.\n\nУслуга: {booking.service}\nДата: {fmt_date(booking.date)}\nВремя: {booking.time}",
        reply_markup=back_to_menu_kb(),
    )
    cancel_reminder(context.application, booking_id)
    try:
        await context.bot.send_message(
            chat_id=booking.user_id,
            text=(
                f"❌ Ваша запись была отменена администратором.\n\n"
                f"Услуга: {booking.service}\n"
                f"Дата: {fmt_date(booking.date)}\n"
                f"Время: {booking.time}\n\n"
                "Пожалуйста, свяжитесь с нами для уточнения деталей."
            ),
        )
    except Exception as exc:
        logger.error("Failed to notify client about cancellation: %s", exc)

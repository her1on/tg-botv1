import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import database
from config import OWNER_IDS
from database import AppointmentRow
from models import Booking
from keyboards import back_to_menu_kb
from reminders import cancel_reminder
from utils import fmt_date

logger = logging.getLogger(__name__)

_MAX_MSG = 4000
_MAX_BUTTONS = 40


def _booking_lines(bookings: list[Booking]) -> list[str]:
    lines = []
    current_date = None
    for b in bookings:
        if b.date != current_date:
            current_date = b.date
            lines.append(f"\n📅 {fmt_date(b.date)}")
        uname = (
            f"{b.full_name} (@{b.username})"
            if b.username and b.full_name
            else b.full_name or f"@{b.username}"
        )
        lines.append(f"  {b.time} — {b.service} | {uname} {b.phone}")
    return lines


def _appointment_lines(appointments: list[AppointmentRow]) -> list[str]:
    lines = []
    current_date = None
    for a in appointments:
        date_str = str(a["appointment_date"])
        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n📅 {fmt_date(date_str)}")
        time_str = str(a["appointment_time"])[:5]
        lines.append(f"  {time_str} — {a['service']} | {a['name']} {a['phone']}")
    return lines


def _split_text(header: str, lines: list[str]) -> list[str]:
    chunks, current = [], header
    for line in lines:
        if len(current) + len(line) + 1 > _MAX_MSG:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line
    if current:
        chunks.append(current)
    return chunks


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("У вас нет доступа.")
        return
    bookings, appointments = await asyncio.gather(
        asyncio.to_thread(database.get_all_upcoming_bookings),
        asyncio.to_thread(database.get_all_upcoming_appointments),
    )
    if not bookings and not appointments:
        await update.message.reply_text("Предстоящих записей нет.")
        return
    messages = []
    if bookings:
        messages.extend(_split_text("🤖 Записи через бота:", _booking_lines(bookings)))
    if appointments:
        messages.extend(_split_text("🌐 Записи с сайта:", _appointment_lines(appointments)))
    for msg in messages:
        await update.message.reply_text(msg)


async def cb_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    bookings, appointments = await asyncio.gather(
        asyncio.to_thread(database.get_all_upcoming_bookings),
        asyncio.to_thread(database.get_all_upcoming_appointments),
    )
    if not bookings and not appointments:
        await query.edit_message_text("Предстоящих записей нет.", reply_markup=back_to_menu_kb())
        return

    visible = bookings[:_MAX_BUTTONS]
    lines = []
    if visible:
        lines.append("🤖 Записи через бота:")
        lines.extend(_booking_lines(visible))
        if len(bookings) > _MAX_BUTTONS:
            lines.append(f"\n...и ещё {len(bookings) - _MAX_BUTTONS}. Используйте /admin для полного списка.")
    if appointments:
        lines.append("\n🌐 Записи с сайта:")
        lines.extend(_appointment_lines(appointments))

    keyboard = [
        [InlineKeyboardButton(
            f"❌ {fmt_date(b.date)} {b.time} — {b.service}",
            callback_data=f"owner_cancel_ask:{b.id}",
        )]
        for b in visible
    ]
    visible_appointments = appointments[:_MAX_BUTTONS]
    for a in visible_appointments:
        keyboard.append([InlineKeyboardButton(
            f"🌐 ❌ {fmt_date(str(a['appointment_date']))} {str(a['appointment_time'])[:5]} — {a['service']}",
            callback_data=f"owner_cancel_web_ask:{a['id']}",
        )])
    if len(appointments) > _MAX_BUTTONS:
        lines.append(f"\n...и ещё {len(appointments) - _MAX_BUTTONS} веб-записей. Используйте /admin для полного списка.")
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="menu")])

    text = "\n".join(lines)
    await query.edit_message_text(text[:_MAX_MSG], reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_owner_cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    try:
        booking_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Некорректные данные.", show_alert=True)
        return
    booking = await asyncio.to_thread(database.get_booking_by_id, booking_id)
    if not booking:
        await query.answer("Запись не найдена.", show_alert=True)
        return
    await query.answer()
    uname = f"@{booking.username}" if booking.username else booking.full_name
    try:
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
    except BadRequest:
        pass


async def cb_owner_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    try:
        booking_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Некорректные данные.", show_alert=True)
        return
    await query.answer()
    booking = await asyncio.to_thread(database.cancel_booking, booking_id)
    if not booking:
        try:
            await query.edit_message_text("Не удалось отменить запись.", reply_markup=back_to_menu_kb())
        except BadRequest:
            pass
        return
    try:
        await query.edit_message_text(
            f"Запись отменена.\n\nУслуга: {booking.service}\nДата: {fmt_date(booking.date)}\nВремя: {booking.time}",
            reply_markup=back_to_menu_kb(),
        )
    except BadRequest:
        pass
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


async def cb_owner_cancel_web_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    appointment_id = query.data.split(":", 1)[1]
    record = await asyncio.to_thread(database.get_appointment_by_id, appointment_id)
    if not record:
        await query.answer("Запись не найдена.", show_alert=True)
        return
    await query.answer()
    date_str = str(record["appointment_date"])
    time_str = str(record["appointment_time"])[:5]
    try:
        await query.edit_message_text(
            f"Отменить запись с сайта?\n\n"
            f"Клиент: {record['name']}\n"
            f"Телефон: {record['phone']}\n"
            f"Услуга: {record['service']}\n"
            f"Дата: {fmt_date(date_str)}\n"
            f"Время: {time_str}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Да, отменить", callback_data=f"owner_cancel_web:{appointment_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="admin"),
            ]]),
        )
    except BadRequest:
        pass


async def cb_owner_cancel_web_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id not in OWNER_IDS:
        await query.answer("Нет доступа.", show_alert=True)
        return
    appointment_id = query.data.split(":", 1)[1]
    await query.answer()
    record = await asyncio.to_thread(database.cancel_appointment, appointment_id)
    if not record:
        try:
            await query.edit_message_text("Не удалось отменить запись.", reply_markup=back_to_menu_kb())
        except BadRequest:
            pass
        return
    date_str = str(record["appointment_date"])
    time_str = str(record["appointment_time"])[:5]
    try:
        await query.edit_message_text(
            f"Запись с сайта отменена.\n\n"
            f"Клиент: {record['name']}\n"
            f"Услуга: {record['service']}\n"
            f"Дата: {fmt_date(date_str)}\n"
            f"Время: {time_str}",
            reply_markup=back_to_menu_kb(),
        )
    except BadRequest:
        pass

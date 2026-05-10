import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler

import database
from config import SALON_NAME
from models import Booking
from keyboards import back_to_menu_kb, main_menu_kb
from reminders import cancel_reminder
from utils import fmt_date, notify_owner


def _build_my_bookings(bookings: list[Booking]) -> tuple[str, InlineKeyboardMarkup]:
    lines = ["Ваши предстоящие записи:\n"]
    keyboard = []
    for b in bookings:
        lines.append(f"📌 {fmt_date(b.date)} в {b.time} — {b.service}")
        keyboard.append([InlineKeyboardButton(
            f"❌ Отменить {fmt_date(b.date)} {b.time}",
            callback_data=f"cancel_ask:{b.id}",
        )])
    keyboard.append([InlineKeyboardButton("← Главное меню", callback_data="menu")])
    return "\n".join(lines), InlineKeyboardMarkup(keyboard)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Добро пожаловать в {SALON_NAME} ✂️💅\n\n"
        "Выберите действие:",
        reply_markup=main_menu_kb(user.id),
    )


async def cb_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    bookings = await asyncio.to_thread(database.get_user_bookings, update.effective_user.id)
    if not bookings:
        await query.edit_message_text("У вас нет предстоящих записей.", reply_markup=back_to_menu_kb())
        return
    text, markup = _build_my_bookings(bookings)
    await query.edit_message_text(text, reply_markup=markup)


async def cb_cancel_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        booking_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Некорректные данные.", show_alert=True)
        return
    booking = await asyncio.to_thread(database.get_booking_by_id, booking_id)
    if not booking or booking.user_id != update.effective_user.id:
        await query.answer("Запись не найдена.", show_alert=True)
        try:
            await query.edit_message_text("Запись не найдена или уже отменена.", reply_markup=back_to_menu_kb())
        except BadRequest:
            pass
        return
    await query.answer()
    try:
        await query.edit_message_text(
            f"Вы уверены, что хотите отменить запись?\n\n"
            f"Услуга: {booking.service}\n"
            f"Дата: {fmt_date(booking.date)}\n"
            f"Время: {booking.time}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Да, отменить", callback_data=f"cancel_confirm:{booking_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="my_bookings"),
            ]]),
        )
    except BadRequest:
        pass


async def cb_cancel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        booking_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Некорректные данные.", show_alert=True)
        return
    await query.answer()
    user = update.effective_user
    booking = await asyncio.to_thread(database.cancel_booking, booking_id, user.id)
    if not booking:
        try:
            await query.edit_message_text("Не удалось отменить запись.", reply_markup=main_menu_kb(user.id))
        except BadRequest:
            pass
        return
    try:
        await query.edit_message_text(
            f"Запись отменена.\n\n"
            f"Услуга: {booking.service}\n"
            f"Дата: {fmt_date(booking.date)}\n"
            f"Время: {booking.time}",
            reply_markup=main_menu_kb(user.id),
        )
    except BadRequest:
        pass
    cancel_reminder(context.application, booking_id)
    uname = f"@{user.username}" if user.username else user.full_name
    await notify_owner(
        context,
        f"❌ Отмена записи!\n\nКлиент: {uname}\nУслуга: {booking.service}\nДата: {fmt_date(booking.date)}\nВремя: {booking.time}",
    )


async def cmd_my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bookings = await asyncio.to_thread(database.get_user_bookings, update.effective_user.id)
    if not bookings:
        await update.message.reply_text("У вас нет предстоящих записей.", reply_markup=back_to_menu_kb())
        return
    text, markup = _build_my_bookings(bookings)
    await update.message.reply_text(text, reply_markup=markup)


async def cb_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Выберите действие:", reply_markup=main_menu_kb(update.effective_user.id))
    return ConversationHandler.END

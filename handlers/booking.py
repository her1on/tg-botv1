import asyncio
from collections import defaultdict
from datetime import date as date_type, datetime
from time import monotonic
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, ConversationHandler

import database
from config import SALON_NAME, SERVICES, TIMEZONE
from keyboards import confirm_kb, dates_kb, main_menu_kb, name_kb, phone_kb, services_kb, times_kb
from reminders import schedule_reminder
from states import CONFIRM, ENTER_NAME, ENTER_PHONE, SELECT_DATE, SELECT_SERVICE, SELECT_TIME
from utils import fmt_date, is_valid_phone, notify_owner

_booking_rate: dict[int, list[float]] = defaultdict(list)
_MAX_BOOKINGS_PER_HOUR = 3
_RATE_WINDOW = 3600.0


def _is_rate_limited(user_id: int) -> bool:
    now = monotonic()
    timestamps = [t for t in _booking_rate[user_id] if now - t < _RATE_WINDOW]
    _booking_rate[user_id] = timestamps
    if len(timestamps) >= _MAX_BOOKINGS_PER_HOUR:
        return True
    _booking_rate[user_id].append(now)
    return False


async def cb_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("name_msg_id", None)
    context.user_data.pop("phone_msg_id", None)
    await query.edit_message_text("Выберите услугу:", reply_markup=services_kb())
    return SELECT_SERVICE


async def cmd_book(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("name_msg_id", None)
    context.user_data.pop("phone_msg_id", None)
    await update.message.reply_text("Выберите услугу:", reply_markup=services_kb())
    return SELECT_SERVICE


async def cb_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try:
        idx = int(query.data.split(":", 1)[1])
        service = SERVICES[idx]
    except (ValueError, IndexError):
        await query.answer("Список услуг обновился. Начните заново.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    context.user_data["service"] = service
    await query.edit_message_text(f"Услуга: {service}\n\nВыберите дату:", reply_markup=dates_kb())
    return SELECT_DATE


async def cb_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    date_str = query.data.split(":", 1)[1]
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        if parsed < datetime.now(ZoneInfo(TIMEZONE)).date():
            await query.answer("Эта дата уже прошла.", show_alert=True)
            return SELECT_DATE
    except ValueError:
        await query.answer()
        return SELECT_DATE
    await query.answer()
    context.user_data["date"] = date_str
    booked = set(await asyncio.to_thread(database.get_booked_times, date_str))
    await query.edit_message_text(
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {fmt_date(date_str)}\n\n"
        "Выберите время:",
        reply_markup=times_kb(date_str, booked),
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
        "Введите ваше имя:",
        reply_markup=name_kb(),
    )
    context.user_data["name_msg_id"] = msg.message_id
    return ENTER_NAME


async def cb_name_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 20:
        await update.message.reply_text("Введите имя (от 2 до 20 символов).")
        return ENTER_NAME
    context.user_data["name"] = name
    text = (
        f"Услуга: {context.user_data['service']}\n"
        f"Дата: {fmt_date(context.user_data['date'])}\n"
        f"Время: {context.user_data['time']}\n"
        f"Имя: {name}\n\n"
        "Введите ваш номер телефона в формате 89XXXXXXXXX:"
    )
    name_msg_id = context.user_data.get("name_msg_id")
    if name_msg_id:
        try:
            msg = await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=name_msg_id,
                text=text,
                reply_markup=phone_kb(),
            )
            context.user_data["phone_msg_id"] = msg.message_id
        except BadRequest:
            msg = await update.message.reply_text(text, reply_markup=phone_kb())
            context.user_data["phone_msg_id"] = msg.message_id
    else:
        msg = await update.message.reply_text(text, reply_markup=phone_kb())
        context.user_data["phone_msg_id"] = msg.message_id
    return ENTER_PHONE


async def cb_phone_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    if not is_valid_phone(phone):
        await update.message.reply_text("Введите корректный номер телефона (7–15 цифр).")
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
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=phone_msg_id,
                text=text,
                reply_markup=confirm_kb(),
            )
        except BadRequest:
            await update.message.reply_text(text, reply_markup=confirm_kb())
    else:
        await update.message.reply_text(text, reply_markup=confirm_kb())
    return CONFIRM


async def cb_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ud = context.user_data
    service = ud.get("service")
    date_str = ud.get("date")
    time_str = ud.get("time")
    phone = ud.get("phone")
    name = (ud.get("name") or user.full_name or "").strip()

    if not all([service, date_str, time_str, phone]) or not name:
        await query.edit_message_text(
            "Что-то пошло не так. Пожалуйста, начните запись заново.",
            reply_markup=main_menu_kb(user.id),
        )
        context.user_data.clear()
        return ConversationHandler.END

    if _is_rate_limited(user.id):
        await query.edit_message_text(
            "Вы создаёте записи слишком часто. Попробуйте через час.",
            reply_markup=main_menu_kb(user.id),
        )
        context.user_data.clear()
        return ConversationHandler.END

    booking_id = await asyncio.to_thread(
        database.add_booking,
        user.id, user.username or "", name, phone, service, date_str, time_str,
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
        f"Клиент: {name} ({uname})\n"
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


async def cb_back_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_str = context.user_data.get("date", "")
    time_str = context.user_data.get("time", "")
    msg = await query.edit_message_text(
        f"Услуга: {context.user_data.get('service', '')}\n"
        f"Дата: {fmt_date(date_str) if date_str else '—'}\n"
        f"Время: {time_str}\n\n"
        "Введите ваше имя:",
        reply_markup=name_kb(),
    )
    context.user_data["name_msg_id"] = msg.message_id
    return ENTER_NAME


async def cb_back_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    date_str = context.user_data.get("date", "")
    service = context.user_data.get("service", "")
    booked = set(await asyncio.to_thread(database.get_booked_times, date_str)) if date_str else set()
    await query.edit_message_text(
        f"Услуга: {service}\n"
        f"Дата: {fmt_date(date_str) if date_str else '—'}\n\n"
        "Выберите время:",
        reply_markup=times_kb(date_str, booked),
    )
    return SELECT_TIME

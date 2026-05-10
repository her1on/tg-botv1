from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import OWNER_IDS, SERVICES, TIME_SLOTS, TIMEZONE, WORKING_DAYS


def main_menu_kb(user_id: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
    ]
    if user_id in OWNER_IDS:
        rows.append([InlineKeyboardButton("🔧 Панель владельца", callback_data="admin")])
    return InlineKeyboardMarkup(rows)


def services_kb() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(SERVICES), 2):
        row = [InlineKeyboardButton(SERVICES[i], callback_data=f"svc:{i}")]
        if i + 1 < len(SERVICES):
            row.append(InlineKeyboardButton(SERVICES[i + 1], callback_data=f"svc:{i + 1}"))
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


def times_kb(date_str: str, booked: set[str]) -> InlineKeyboardMarkup:
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


def name_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back:time")]])


def phone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back:name")]])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
        InlineKeyboardButton("❌ Отмена", callback_data="back:main"),
    ]])


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Главное меню", callback_data="menu")]])

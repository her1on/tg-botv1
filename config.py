import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
SALON_NAME: str = os.getenv("SALON_NAME", "Салон красоты")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
SERVICES: list[str] = [s.strip() for s in os.getenv("SERVICES", "Стрижка,Окрашивание,Маникюр,Педикюр,Укладка,Уход за лицом").split(",")]
TIME_SLOTS: list[str] = [t.strip() for t in os.getenv("TIME_SLOTS", "10:00,11:00,12:00,13:00,14:00,15:00,16:00,17:00,18:00,19:00,20:00").split(",")]


def _parse_owner_ids() -> list[int]:
    raw = os.getenv("OWNER_IDS", os.getenv("OWNER_ID", ""))
    result = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                result.append(int(part))
            except ValueError:
                pass
    return result


def _parse_working_days() -> list[int]:
    raw = os.getenv("WORKING_DAYS", "0,1,2,3,4,5")
    try:
        days = [int(d.strip()) for d in raw.split(",") if d.strip()]
    except ValueError:
        raise ValueError(f"WORKING_DAYS содержит нечисловые значения: {raw!r}")
    invalid = [d for d in days if not (0 <= d <= 6)]
    if invalid:
        raise ValueError(f"WORKING_DAYS: значения вне диапазона 0–6: {invalid}")
    return days


OWNER_IDS: list[int] = _parse_owner_ids()
WORKING_DAYS: list[int] = _parse_working_days()

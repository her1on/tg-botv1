import logging
from datetime import datetime

from telegram.ext import ContextTypes

from config import OWNER_IDS

logger = logging.getLogger(__name__)


def fmt_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_str


def is_valid_phone(phone: str) -> bool:
    return 7 <= sum(c.isdigit() for c in phone) <= 15


async def notify_owner(context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    for owner_id in OWNER_IDS:
        if not owner_id:
            continue
        try:
            await context.bot.send_message(chat_id=owner_id, text=text)
        except Exception as exc:
            logger.error("Owner notification failed for %d: %s", owner_id, exc)

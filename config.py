import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
SALON_NAME: str = os.getenv("SALON_NAME", "Салон красоты")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
WORKING_DAYS: list[int] = [int(d.strip()) for d in os.getenv("WORKING_DAYS", "0,1,2,3,4,5").split(",")]
SERVICES: list[str] = [s.strip() for s in os.getenv("SERVICES", "Стрижка,Окрашивание,Маникюр,Педикюр,Укладка,Уход за лицом").split(",")]
TIME_SLOTS: list[str] = [t.strip() for t in os.getenv("TIME_SLOTS", "09:00,10:00,11:00,12:00,13:00,14:00,15:00,16:00,17:00,18:00").split(",")]

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "/data/tasks.db")
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Europe/Moscow")
DEFAULT_DIGEST_TIME = os.getenv("DEFAULT_DIGEST_TIME", "09:00")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Check .env")
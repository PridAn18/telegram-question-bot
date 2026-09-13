import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = [
    int(item)
    for item in os.getenv("ADMIN_IDS", "").split(",")
    if item.strip().isdigit()
]

DATABASE_PATH = os.getenv(
    "DATABASE_PATH", os.path.join(BASE_DIR, "data", "questions.db")
)

LOG_PATH = os.getenv("LOG_PATH", os.path.join(BASE_DIR, "logs", "bot.log"))
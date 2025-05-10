import os
from dotenv import load_dotenv

load_dotenv()
print("✅ Файл .env загружен")

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# AIzaSyDga55CfpHMz5IRVHFJWkptdMc37E8DuYc
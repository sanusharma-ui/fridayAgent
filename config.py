"""Local configuration. Set secrets through environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

APP_NAME = os.getenv("ASSISTANT_NAME", "NEO")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Nagpur")
AI_ENDPOINT_URL = os.getenv(
    "AI_ENDPOINT_URL", "https://preconceptional-roland-nondisposable.ngrok-free.dev"
).rstrip("/")
FRIDAY_API_KEY = os.getenv("FRIDAY_API_KEY", "")

# Telegram access is opt-in. Keep the token in .env, never in source control.
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ALLOWED_USER_IDS = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
TELEGRAM_WHISPER_MODEL = os.getenv("TELEGRAM_WHISPER_MODEL", "base").strip()
TELEGRAM_VOICE_LANGUAGE = os.getenv("TELEGRAM_VOICE_LANGUAGE", "").strip()

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

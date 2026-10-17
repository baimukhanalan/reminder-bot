from dataclasses import dataclass
import os
from pathlib import Path
from typing import FrozenSet

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openai_api_key: str
    database_path: Path
    default_timezone: str
    text_model: str
    transcribe_model: str
    allowed_user_ids: FrozenSet[int]
    webapp_url: str
    webapp_host: str
    webapp_port: int
    dev_user_id: int


def load_settings() -> Settings:
    load_dotenv(".env.local")
    load_dotenv()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    raw_ids = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "")
    allowed_ids = frozenset(
        int(item.strip()) for item in raw_ids.split(",") if item.strip()
    )
    return Settings(
        telegram_token=telegram_token,
        openai_api_key=openai_api_key,
        database_path=Path(os.getenv("DATABASE_PATH", "data/assistant.db")),
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Almaty"),
        text_model=os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini"),
        transcribe_model=os.getenv(
            "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
        ),
        allowed_user_ids=allowed_ids,
        webapp_url=os.getenv("WEBAPP_URL", "").strip().rstrip("/"),
        webapp_host=os.getenv("WEBAPP_HOST", "0.0.0.0"),
        webapp_port=int(os.getenv("PORT", os.getenv("WEBAPP_PORT", "8080"))),
        dev_user_id=int(os.getenv("DEV_TELEGRAM_USER_ID", "0") or "0"),
    )

"""تحميل الإعدادات من ملف البيئة."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OWNER_FILE = DATA_DIR / "owner.json"


@dataclass(frozen=True)
class Config:
    telegram_token: str
    notion_token: str
    notion_database_id: str
    timezone: str

    @classmethod
    def load(cls) -> "Config":
        load_dotenv(PROJECT_ROOT / ".env")

        telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        notion_token = os.environ.get("NOTION_TOKEN", "").strip()
        notion_database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
        timezone = os.environ.get("TIMEZONE", "Asia/Riyadh").strip()

        missing = [
            name
            for name, value in [
                ("TELEGRAM_BOT_TOKEN", telegram_token),
                ("NOTION_TOKEN", notion_token),
                ("NOTION_DATABASE_ID", notion_database_id),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in the values."
            )

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        return cls(
            telegram_token=telegram_token,
            notion_token=notion_token,
            notion_database_id=notion_database_id,
            timezone=timezone,
        )

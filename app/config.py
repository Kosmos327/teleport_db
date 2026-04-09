from __future__ import annotations

import json
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram
    BOT_TOKEN: str

    # PostgreSQL
    DATABASE_URL: str  # postgresql+asyncpg://...

    # YooKassa
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_RETURN_URL: str = ""

    # Timezone
    TIMEZONE: str = "Europe/Moscow"

    # Admins
    ADMIN_IDS: List[int] = []
    ADMIN_USERNAME: str = ""  # without @

    # Closed chat for invite links
    ACCESS_CHAT_ID: int = 0

    # Webhook / server
    WEBHOOK_HOST: str = ""  # empty → use polling (dev mode)
    BOT_WEBHOOK_PATH: str = "/webhook/bot"
    YOOKASSA_WEBHOOK_PATH: str = "/webhook/yookassa"
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080

    # How many minutes a pending payment is considered reusable
    PAYMENT_REUSE_MINUTES: int = 30

    # Days before expiry to send pre-notice
    PRENOTICE_DAYS: int = 3

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> List[int]:
        if isinstance(v, str):
            return json.loads(v)
        return v  # type: ignore[return-value]


settings = Settings()

from __future__ import annotations

import json
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None)

    # Telegram
    BOT_TOKEN: str
    ACCESS_CHAT_ID: int
    ADMIN_USERNAME: str = ""  # without @
    ADMIN_IDS: List[int] = []

    # PostgreSQL
    DATABASE_URL: str  # postgresql+asyncpg://...

    # YooKassa
    YOOKASSA_SHOP_ID: str
    YOOKASSA_API_KEY: str
    PUBLIC_BASE_URL: str = ""  # empty → use polling mode (dev)

    # Webhook / server
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080

    # Receipt settings
    TAX_SYSTEM_CODE: int = 1
    VAT_CODE: int = 1

    # Timezone
    TIMEZONE: str = "Europe/Moscow"

    # Pending payment reuse window
    PENDING_REUSE_MINUTES: int = 30

    # Recurring payments
    RECURRING_ENABLED: bool = False

    # Autopay
    AUTOPAY_ENABLED: bool = False
    AUTOPAY_CHARGE_HOUR: int = 9
    AUTOPAY_CHARGE_MINUTE: int = 0
    AUTOPAY_PRENOTICE_DAYS: int = 3
    AUTOPAY_RETRY_MINUTES: int = 60
    AUTOPAY_MAX_RETRIES: int = 3

    # Subscription expiry pre-notice
    SUBSCRIPTION_PRENOTICE_DAYS: int = 3
    PRENOTICE_CHECK_INTERVAL_SECONDS: int = 3600

    # Legal URLs
    POLICY_URL: str = ""
    OFFER_URL: str = ""

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: object) -> List[int]:
        if isinstance(v, str):
            return json.loads(v)
        return v  # type: ignore[return-value]


settings = Settings()

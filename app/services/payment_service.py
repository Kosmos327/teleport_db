"""YooKassa payment service."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import yookassa
from yookassa import Configuration, Payment

from app.config import settings
from app.tariffs import Tariff

# Configure YooKassa once at import time
Configuration.configure(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY)


def _create_payment_sync(
    tariff: Tariff,
    tg_user_id: int,
    return_url: str,
    is_renew: bool = False,
    payment_method_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Synchronous YooKassa payment creation (wrapped for asyncio below)."""
    payload: dict[str, Any] = {
        "amount": {
            "value": f"{tariff['price']:.2f}",
            "currency": tariff["currency"],
        },
        "capture": True,
        "description": f"{'Автопродление: ' if is_renew else ''}{tariff['name']}",
        "metadata": {
            "tg_user_id": str(tg_user_id),
            "tariff": tariff["code"],
            "is_renew": str(is_renew).lower(),
        },
    }

    if payment_method_id:
        # Autopay with saved card
        payload["payment_method_id"] = payment_method_id
    else:
        # Interactive payment
        payload["confirmation"] = {"type": "redirect", "return_url": return_url}
        payload["save_payment_method"] = True

    key = idempotency_key or str(uuid.uuid4())
    result = Payment.create(payload, key)
    return result.dict()  # type: ignore[return-value]


async def create_payment(
    tariff: Tariff,
    tg_user_id: int,
    return_url: str | None = None,
    is_renew: bool = False,
    payment_method_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Async wrapper around YooKassa Payment.create."""
    effective_return_url = return_url or settings.YOOKASSA_RETURN_URL
    return await asyncio.to_thread(
        _create_payment_sync,
        tariff,
        tg_user_id,
        effective_return_url,
        is_renew,
        payment_method_id,
        idempotency_key,
    )


def _fetch_payment_sync(payment_id: str) -> dict[str, Any]:
    result = Payment.find_one(payment_id)
    return result.dict()  # type: ignore[return-value]


async def fetch_payment(payment_id: str) -> dict[str, Any]:
    """Async wrapper: fetch payment from YooKassa API by ID."""
    return await asyncio.to_thread(_fetch_payment_sync, payment_id)


def _cancel_payment_sync(payment_id: str, idempotency_key: str) -> dict[str, Any]:
    result = Payment.cancel(payment_id, idempotency_key)
    return result.dict()  # type: ignore[return-value]


async def cancel_payment(payment_id: str) -> dict[str, Any]:
    """Cancel a pending payment."""
    return await asyncio.to_thread(
        _cancel_payment_sync, payment_id, str(uuid.uuid4())
    )

"""Payment repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Payment


async def create(
    session: AsyncSession,
    payment_id: str,
    tg_user_id: int,
    username: str | None,
    tariff: str,
    confirmation_url: str,
    is_renew: bool = False,
) -> Payment:
    payment = Payment(
        payment_id=payment_id,
        tg_user_id=tg_user_id,
        username=username,
        tariff=tariff,
        status="pending",
        confirmation_url=confirmation_url,
        is_renew=is_renew,
    )
    session.add(payment)
    await session.flush()
    return payment


async def get(session: AsyncSession, payment_id: str) -> Payment | None:
    return await session.get(Payment, payment_id)


async def get_recent_pending(
    session: AsyncSession,
    tg_user_id: int,
    tariff: str,
    minutes: int = 30,
) -> Payment | None:
    """Return a pending payment for the same user+tariff created within *minutes*."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)
    result = await session.execute(
        select(Payment)
        .where(
            Payment.tg_user_id == tg_user_id,
            Payment.tariff == tariff,
            Payment.status == "pending",
            Payment.created_at >= cutoff,
        )
        .order_by(Payment.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def update_status(
    session: AsyncSession,
    payment_id: str,
    status: str,
    paid_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Payment | None:
    payment = await session.get(Payment, payment_id)
    if payment is None:
        return None
    payment.status = status
    if paid_at is not None:
        payment.paid_at = paid_at
    if expires_at is not None:
        payment.expires_at = expires_at
    return payment


async def list_by_user(session: AsyncSession, tg_user_id: int) -> list[Payment]:
    result = await session.execute(
        select(Payment)
        .where(Payment.tg_user_id == tg_user_id)
        .order_by(Payment.created_at.desc())
    )
    return list(result.scalars().all())

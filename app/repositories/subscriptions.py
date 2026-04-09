"""Subscription repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Subscription


async def create(
    session: AsyncSession,
    telegram_user_id: int,
    tariff_code: str,
    starts_at: datetime,
    expires_at: datetime,
    source_payment_id: str,
    auto_renew_enabled: bool = True,
) -> Subscription:
    sub = Subscription(
        telegram_user_id=telegram_user_id,
        tariff_code=tariff_code,
        starts_at=starts_at,
        expires_at=expires_at,
        status="active",
        source_payment_id=source_payment_id,
        auto_renew_enabled=auto_renew_enabled,
    )
    session.add(sub)
    await session.flush()
    return sub


async def get_active(
    session: AsyncSession, telegram_user_id: int
) -> Subscription | None:
    """Return the current active subscription."""
    now = datetime.now(tz=timezone.utc)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.telegram_user_id == telegram_user_id,
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_latest(
    session: AsyncSession, telegram_user_id: int
) -> Subscription | None:
    """Return the most recent subscription regardless of status."""
    result = await session.execute(
        select(Subscription)
        .where(Subscription.telegram_user_id == telegram_user_id)
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def expire_old(session: AsyncSession) -> int:
    """Mark subscriptions that have passed their expiry date as 'expired'.

    Returns the count of updated records.
    """
    from sqlalchemy import update

    now = datetime.now(tz=timezone.utc)
    result = await session.execute(
        update(Subscription)
        .where(Subscription.status == "active", Subscription.expires_at <= now)
        .values(status="expired", updated_at=now)
        .returning(Subscription.id)
    )
    rows = result.all()
    return len(rows)


async def set_auto_renew(
    session: AsyncSession, sub_id: int, enabled: bool
) -> None:
    sub = await session.get(Subscription, sub_id)
    if sub:
        sub.auto_renew_enabled = enabled
        sub.updated_at = datetime.now(tz=timezone.utc)


async def list_expiring_soon(
    session: AsyncSession, days: int = 3
) -> list[Subscription]:
    """Subscriptions that expire within *days* days and are still active."""
    now = datetime.now(tz=timezone.utc)
    deadline = now + timedelta(days=days)
    result = await session.execute(
        select(Subscription).where(
            Subscription.status == "active",
            Subscription.expires_at > now,
            Subscription.expires_at <= deadline,
        )
    )
    return list(result.scalars().all())

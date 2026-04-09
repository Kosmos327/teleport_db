"""PaymentMethod repository (saved cards for auto-renewal)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import PaymentMethod


async def get_active(session: AsyncSession, tg_user_id: int) -> PaymentMethod | None:
    """Return the active payment method for a user."""
    result = await session.execute(
        select(PaymentMethod)
        .where(PaymentMethod.tg_user_id == tg_user_id, PaymentMethod.active == True)
        .order_by(PaymentMethod.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_by_method_id(
    session: AsyncSession, payment_method_id: str
) -> PaymentMethod | None:
    result = await session.execute(
        select(PaymentMethod).where(
            PaymentMethod.payment_method_id == payment_method_id
        )
    )
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    tg_user_id: int,
    username: str | None,
    first_name: str | None,
    payment_method_id: str,
    last_payment_id: str,
    next_charge_at: datetime,
) -> PaymentMethod:
    """Create or update a saved payment method."""
    pm = await get_by_method_id(session, payment_method_id)
    if pm is None:
        pm = PaymentMethod(
            tg_user_id=tg_user_id,
            username=username,
            first_name=first_name,
            payment_method_id=payment_method_id,
            active=True,
            last_payment_id=last_payment_id,
            last_status="succeeded",
            next_charge_at=next_charge_at,
            last_cycle=1,
            retry_count=0,
        )
        session.add(pm)
    else:
        pm.active = True
        pm.last_payment_id = last_payment_id
        pm.last_status = "succeeded"
        pm.next_charge_at = next_charge_at
        pm.last_cycle += 1
        pm.retry_count = 0
        pm.updated_at = datetime.now(tz=timezone.utc)
    await session.flush()
    return pm


async def deactivate(session: AsyncSession, tg_user_id: int) -> bool:
    """Deactivate all payment methods for a user."""
    pm = await get_active(session, tg_user_id)
    if pm is None:
        return False
    pm.active = False
    pm.updated_at = datetime.now(tz=timezone.utc)
    return True


async def record_autopay_attempt(
    session: AsyncSession,
    pm: PaymentMethod,
    payment_id: str,
    status: str,
) -> None:
    pm.last_payment_id = payment_id
    pm.last_status = status
    if status == "succeeded":
        pm.retry_count = 0
        pm.last_cycle += 1
    else:
        pm.retry_count += 1
    pm.updated_at = datetime.now(tz=timezone.utc)


async def list_due_for_charge(session: AsyncSession) -> list[PaymentMethod]:
    """All active payment methods whose next_charge_at is in the past."""
    now = datetime.now(tz=timezone.utc)
    result = await session.execute(
        select(PaymentMethod).where(
            PaymentMethod.active == True,
            PaymentMethod.next_charge_at <= now,
        )
    )
    return list(result.scalars().all())

"""EventLog repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import EventLog


async def log(
    session: AsyncSession,
    event_type: str,
    telegram_user_id: int | None = None,
    **payload: Any,
) -> EventLog:
    entry = EventLog(
        event_type=event_type,
        telegram_user_id=telegram_user_id,
        payload=payload or None,
    )
    session.add(entry)
    await session.flush()
    return entry

"""InviteLink repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import InviteLink


async def create(
    session: AsyncSession,
    telegram_user_id: int,
    chat_id: int,
    invite_link: str,
    expires_at: datetime | None = None,
) -> InviteLink:
    link = InviteLink(
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        invite_link=invite_link,
        expires_at=expires_at,
    )
    session.add(link)
    await session.flush()
    return link


async def list_by_user(
    session: AsyncSession, telegram_user_id: int
) -> list[InviteLink]:
    result = await session.execute(
        select(InviteLink)
        .where(InviteLink.telegram_user_id == telegram_user_id)
        .order_by(InviteLink.created_at.desc())
    )
    return list(result.scalars().all())

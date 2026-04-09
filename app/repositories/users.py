"""User repository."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


async def get_or_create(
    session: AsyncSession,
    tg_user_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    """Return existing user or create a new one."""
    user = await session.get(User, tg_user_id)
    if user is None:
        user = User(id=tg_user_id, username=username, first_name=first_name)
        session.add(user)
        await session.flush()
    else:
        changed = False
        if username is not None and user.username != username:
            user.username = username
            changed = True
        if first_name is not None and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            user.updated_at = datetime.utcnow()
    return user


async def get(session: AsyncSession, tg_user_id: int) -> User | None:
    return await session.get(User, tg_user_id)


async def set_email(session: AsyncSession, tg_user_id: int, email: str) -> None:
    user = await session.get(User, tg_user_id)
    if user:
        user.email = email
        user.updated_at = datetime.utcnow()


async def get_email(session: AsyncSession, tg_user_id: int) -> str | None:
    user = await session.get(User, tg_user_id)
    return user.email if user else None


async def list_all(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User))
    return list(result.scalars().all())

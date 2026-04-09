"""Telegram invite-link service."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from aiogram import Bot
from aiogram.types import ChatInviteLink

from app.config import settings


async def create_invite_link(
    bot: Bot,
    *,
    member_limit: int = 1,
    expire_hours: int = 24,
) -> ChatInviteLink:
    """Create a one-time invite link for ACCESS_CHAT_ID."""
    expire_dt = datetime.now(tz=timezone.utc) + timedelta(hours=expire_hours)
    link = await bot.create_chat_invite_link(
        chat_id=settings.ACCESS_CHAT_ID,
        expire_date=expire_dt,
        member_limit=member_limit,
        creates_join_request=False,
    )
    return link

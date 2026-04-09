"""Timezone-aware datetime utilities."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

import pytz

from app.config import settings

_tz = pytz.timezone(settings.TIMEZONE)


def now_local() -> datetime:
    """Current datetime in the configured timezone."""
    return datetime.now(tz=_tz)


def to_local(dt: datetime) -> datetime:
    """Convert a naive or UTC datetime to the configured timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_tz)


def parse_dt(value: str) -> datetime:
    """Parse ISO-8601 string → aware datetime in local timezone."""
    dt = datetime.fromisoformat(value)
    return to_local(dt)


def add_months_keep_day(dt: datetime, months: int) -> datetime:
    """Add *months* months to *dt*, keeping the same day-of-month.

    If the resulting month has fewer days, uses the last day of that month.
    Timezone info is preserved.
    """
    total_months = dt.month - 1 + months
    year = dt.year + total_months // 12
    month = total_months % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def fmt_dt(dt: datetime | None) -> str:
    """Format datetime for display (localized, no seconds)."""
    if dt is None:
        return "—"
    return to_local(dt).strftime("%d.%m.%Y %H:%M")

"""Time helpers.

The application stores wall-clock local time (single user, single timezone), so
daily/monthly buckets line up with what the user sees on their phone.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ..config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def now_local() -> datetime:
    """Naive local timestamp, used for audit columns and defaults."""
    return datetime.now(local_tz()).replace(tzinfo=None)


def today_local() -> date:
    return datetime.now(local_tz()).date()


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    """Shift a date by whole months, clamping the day to the target month."""
    total = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    first_of_month = date(year, month, 1)
    first_of_next = date(year + (month // 12), (month % 12) + 1, 1)
    day = min(value.day, (first_of_next - first_of_month).days)
    return date(year, month, day)

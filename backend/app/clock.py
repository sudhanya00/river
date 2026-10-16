"""Single source of "now". Everything time-based (return dates, refills, created_at, caught_at) reads it.

In dev mode the clock can be pushed forward with an offset (POST /api/dev/clock) to test returns and
refills without waiting. The offset lives in memory, so restarting the server resets it.
"""
from datetime import datetime, timedelta, timezone

_offset = timedelta(0)


def now() -> datetime:
    return datetime.now(timezone.utc) + _offset


def offset() -> timedelta:
    return _offset


def set_offset(value: timedelta) -> None:
    from .config import get_settings

    if not get_settings().dev_mode:
        raise PermissionError("The clock can only be moved in dev mode.")
    global _offset
    _offset = value

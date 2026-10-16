"""Single source of "now" so a dev clock override can slot in later (phase 2)."""
from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)

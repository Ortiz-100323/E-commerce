import hashlib
import math
from collections.abc import Iterable
from datetime import datetime, timedelta

MAX_FAILURES = 5
WINDOW = timedelta(minutes=15)


def retry_after(failures: Iterable[datetime], now: datetime) -> int | None:
    recent = sorted(moment for moment in failures if now - moment < WINDOW)
    if len(recent) < MAX_FAILURES:
        return None
    oldest_counted = recent[-MAX_FAILURES]
    seconds = (oldest_counted + WINDOW - now).total_seconds()
    return max(1, math.ceil(seconds))


def login_key(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()

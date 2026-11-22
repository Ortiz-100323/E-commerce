import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Self
from uuid import UUID

IDLE_TIMEOUT = timedelta(minutes=30)
ABSOLUTE_LIFETIME = timedelta(hours=8)
TOUCH_EVERY = timedelta(minutes=1)


@dataclass(frozen=True, kw_only=True)
class Session:
    session_id: UUID
    account_id: UUID
    token_hash: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime

    @classmethod
    def start(cls, *, session_id: UUID, account_id: UUID, token_hash: str, at: datetime) -> Self:
        return cls(
            session_id=session_id,
            account_id=account_id,
            token_hash=token_hash,
            created_at=at,
            last_seen_at=at,
            expires_at=at + ABSOLUTE_LIFETIME,
        )

    def is_active(self, now: datetime) -> bool:
        return now < self.expires_at and now < self.last_seen_at + IDLE_TIMEOUT

    def needs_touch(self, now: datetime) -> bool:
        return now - self.last_seen_at >= TOUCH_EVERY

    def touched(self, now: datetime) -> Self:
        return replace(self, last_seen_at=now)


MAX_TOKEN_LENGTH = 128


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

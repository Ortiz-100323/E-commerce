from datetime import UTC, datetime
from typing import Protocol

from ecommerce.shared_kernel.domain.principal import Principal


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class DatabaseProbe(Protocol):
    async def is_up(self) -> bool: ...


class Authenticator(Protocol):
    async def authenticate(self, token: str) -> Principal | None: ...

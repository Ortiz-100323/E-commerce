from datetime import timedelta

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ecommerce.ordering.infrastructure.unit_of_work import DEFAULT_LOCK_TIMEOUT_MS


class CheckoutSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHECKOUT_", extra="ignore")

    idempotency_key_hours: int = Field(default=24, ge=1, le=24 * 30)
    lock_timeout_ms: int = Field(default=DEFAULT_LOCK_TIMEOUT_MS, ge=100, le=60_000)

    @property
    def idempotency_key_lifetime(self) -> timedelta:
        return timedelta(hours=self.idempotency_key_hours)

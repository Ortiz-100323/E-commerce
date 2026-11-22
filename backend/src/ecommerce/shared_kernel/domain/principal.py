from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import DomainError


class Role(StrEnum):
    ADMIN = "ADMIN"
    BUYER = "BUYER"


@dataclass(frozen=True, kw_only=True)
class Principal:
    account_id: UUID
    name: str
    email: str
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN

    @property
    def is_buyer(self) -> bool:
        return self.role is Role.BUYER

    def actor(self) -> Actor:
        return Actor(self.name)


class AuthenticationRequired(DomainError):
    def __init__(self) -> None:
        super().__init__("Log in to continue.")


class AdminRequired(DomainError):
    def __init__(self) -> None:
        super().__init__("This is for administrators only.")


class BuyerRequired(DomainError):
    def __init__(self) -> None:
        super().__init__("This is for customer accounts only.")

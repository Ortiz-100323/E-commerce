from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ecommerce.identity.domain.account import Account
from ecommerce.shared_kernel.domain.principal import Principal, Role

MAX_EMAIL_INPUT = 320
MAX_NAME_INPUT = 400
MAX_PASSWORD_INPUT = 1024


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=MAX_EMAIL_INPUT)
    password: str = Field(max_length=MAX_PASSWORD_INPUT)


class NewAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=MAX_NAME_INPUT)
    email: str = Field(max_length=MAX_EMAIL_INPUT)
    password: str = Field(max_length=MAX_PASSWORD_INPUT)


class AccountResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: Role

    @classmethod
    def of_principal(cls, principal: Principal) -> "AccountResponse":
        return cls(
            id=principal.account_id, name=principal.name, email=principal.email, role=principal.role
        )

    @classmethod
    def of_account(cls, account: Account) -> "AccountResponse":
        return cls.of_principal(account.principal())


class AccountsResponse(BaseModel):
    items: list[AccountResponse]

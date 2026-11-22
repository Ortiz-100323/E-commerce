from uuid import UUID

import pytest

from ecommerce.shared_kernel.domain.errors import DomainError
from ecommerce.shared_kernel.domain.principal import (
    AdminRequired,
    AuthenticationRequired,
    BuyerRequired,
    Principal,
    Role,
)

ACCOUNT = UUID("00000000-0000-4000-8000-0000000000a1")


def test_roles_are_admin_and_buyer_only() -> None:
    assert [role.value for role in Role] == ["ADMIN", "BUYER"]


def test_a_principal_knows_its_role() -> None:
    admin = Principal(account_id=ACCOUNT, name="Ana", email="ana@example.com", role=Role.ADMIN)
    buyer = Principal(account_id=ACCOUNT, name="Bea", email="bea@example.com", role=Role.BUYER)

    assert admin.is_admin and not admin.is_buyer
    assert buyer.is_buyer and not buyer.is_admin


def test_a_principal_names_the_actor_of_its_changes() -> None:
    admin = Principal(account_id=ACCOUNT, name="Ana", email="ana@example.com", role=Role.ADMIN)

    assert admin.actor().name == "Ana"


@pytest.mark.parametrize("error", [AuthenticationRequired(), AdminRequired(), BuyerRequired()])
def test_access_errors_are_domain_errors(error: Exception) -> None:
    assert isinstance(error, DomainError)

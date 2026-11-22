from datetime import UTC, datetime
from uuid import UUID

import pytest

from ecommerce.identity.domain.account import (
    MAX_ACCOUNT_NAME_LENGTH,
    MAX_EMAIL_LENGTH,
    Account,
    AccountId,
    AccountName,
    EmailAddress,
)
from ecommerce.shared_kernel.domain.errors import DomainValidationError
from ecommerce.shared_kernel.domain.principal import Role

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
ID = AccountId(UUID("00000000-0000-4000-8000-0000000000a1"))


def codes(error: DomainValidationError) -> list[tuple[str, str]]:
    return [(issue.field, issue.code) for issue in error.issues]


class TestEmailAddress:
    def test_is_trimmed_and_lower_cased(self) -> None:
        assert EmailAddress("  Ana.Souza@Example.COM ").value == "ana.souza@example.com"

    @pytest.mark.parametrize(
        ("raw", "code"),
        [
            ("", "required"),
            ("   ", "required"),
            ("ana", "invalid_email"),
            ("ana@example", "invalid_email"),
            ("ana @example.com", "invalid_email"),
            ("ana@exa\nmple.com", "control_characters_not_allowed"),
            ("a" * (MAX_EMAIL_LENGTH - 11) + "@example.com", "too_long"),
        ],
    )
    def test_refuses_what_is_not_an_email(self, raw: str, code: str) -> None:
        with pytest.raises(DomainValidationError) as raised:
            EmailAddress(raw)

        assert codes(raised.value) == [("email", code)]


class TestAccountName:
    def test_is_trimmed(self) -> None:
        assert AccountName("  Ana Souza ").value == "Ana Souza"

    @pytest.mark.parametrize(
        ("raw", "code"),
        [
            ("", "required"),
            ("x" * (MAX_ACCOUNT_NAME_LENGTH + 1), "too_long"),
            ("Ana\tSouza", "control_characters_not_allowed"),
        ],
    )
    def test_refuses_bad_names(self, raw: str, code: str) -> None:
        with pytest.raises(DomainValidationError) as raised:
            AccountName(raw)

        assert codes(raised.value) == [("name", code)]


class TestAccount:
    def test_an_admin_is_created_with_the_admin_role(self) -> None:
        account = Account.create(
            account_id=ID,
            name="Ana",
            email="ANA@example.com",
            role=Role.ADMIN,
            password_hash="hash",
            at=NOW,
        )

        assert (account.role, account.email.value, account.name.value) == (
            Role.ADMIN,
            "ana@example.com",
            "Ana",
        )
        assert account.active

    def test_reports_every_invalid_field_at_once(self) -> None:
        with pytest.raises(DomainValidationError) as raised:
            Account.create(
                account_id=ID, name="", email="nope", role=Role.BUYER, password_hash="h", at=NOW
            )

        assert codes(raised.value) == [("name", "required"), ("email", "invalid_email")]

    def test_has_no_way_to_change_its_role(self) -> None:
        account = Account.create(
            account_id=ID,
            name="Bea",
            email="bea@example.com",
            role=Role.BUYER,
            password_hash="h",
            at=NOW,
        )

        with pytest.raises(AttributeError):
            account.__setattr__("role", Role.ADMIN)
        assert not any(
            name.startswith(("promote", "set_role", "change_role")) for name in dir(account)
        )

    def test_becomes_a_principal(self) -> None:
        account = Account.create(
            account_id=ID,
            name="Bea",
            email="bea@example.com",
            role=Role.BUYER,
            password_hash="h",
            at=NOW,
        )

        principal = account.principal()

        assert (principal.account_id, principal.name, principal.role) == (ID, "Bea", Role.BUYER)

    def test_never_shows_its_hash_when_printed(self) -> None:
        account = Account.create(
            account_id=ID,
            name="Bea",
            email="bea@example.com",
            role=Role.BUYER,
            password_hash="scrypt$secret-hash",
            at=NOW,
        )

        assert "secret-hash" not in repr(account)

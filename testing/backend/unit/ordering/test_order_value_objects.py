from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ecommerce.ordering.domain.payment import PaymentCard, luhn_valid
from ecommerce.ordering.domain.value_objects import Customer
from ecommerce.shared_kernel.domain.errors import DomainValidationError

TODAY = date(2026, 11, 22)
APPROVED = "4242 4242 4242 4242"


def card(
    number: str = APPROVED, month: int = 12, year: int = 2030, cvc: str = "123"
) -> PaymentCard:
    return PaymentCard.of(number, month, year, cvc, today=TODAY)


def issues_of(error: pytest.ExceptionInfo[DomainValidationError]) -> list[tuple[str, str]]:
    return [(issue.field, issue.code) for issue in error.value.issues]


def test_a_customer_is_trimmed_and_the_email_lower_cased() -> None:
    customer = Customer.of("  Ana Souza ", " Ana.Souza@Example.COM ")

    assert (customer.name, customer.email) == ("Ana Souza", "ana.souza@example.com")


@pytest.mark.parametrize(
    ("name", "email", "expected"),
    [
        ("", "ana@example.com", [("customer.name", "required")]),
        ("A" * 201, "ana@example.com", [("customer.name", "too_long")]),
        ("Ana\nSouza", "ana@example.com", [("customer.name", "control_characters_not_allowed")]),
        ("Ana", "", [("customer.email", "required")]),
        ("Ana", "ana.example.com", [("customer.email", "invalid_email")]),
        ("Ana", "ana@example", [("customer.email", "invalid_email")]),
        ("Ana", "ana @example.com", [("customer.email", "invalid_email")]),
        ("Ana", "a@" + "b" * 250 + ".com", [("customer.email", "too_long")]),
        ("", "nope", [("customer.name", "required"), ("customer.email", "invalid_email")]),
    ],
)
def test_a_customer_reports_every_problem_at_once(
    name: str, email: str, expected: list[tuple[str, str]]
) -> None:
    with pytest.raises(DomainValidationError) as error:
        Customer.of(name, email)

    assert issues_of(error) == expected


@pytest.mark.parametrize(
    "number", ["4242424242424242", "4000000000000002", "5555555555554444", "378282246310005"]
)
def test_known_test_card_numbers_pass_the_luhn_check(number: str) -> None:
    assert luhn_valid(number)


@given(st.from_regex(r"[0-9]{15}", fullmatch=True))
def test_exactly_one_check_digit_completes_any_number(prefix: str) -> None:
    valid = [digit for digit in "0123456789" if luhn_valid(prefix + digit)]

    assert len(valid) == 1


def test_a_card_keeps_only_digits_and_shows_its_last_four() -> None:
    accepted = card("4242-4242 4242-4242")

    assert accepted.number == "4242424242424242"
    assert accepted.last4 == "4242"


def test_a_card_never_shows_its_number_or_code_when_printed() -> None:
    accepted = card(cvc="987")

    for text in (repr(accepted), str(accepted), f"{accepted}"):
        assert "4242424242424242" not in text
        assert "987" not in text
        assert "4242" in text


@pytest.mark.parametrize(
    ("number", "month", "year", "cvc", "expected"),
    [
        ("4242 4242 4242 4241", 12, 2030, "123", [("payment.card_number", "invalid_card_number")]),
        ("4242", 12, 2030, "123", [("payment.card_number", "invalid_card_number")]),
        ("4242abcd42424242", 12, 2030, "123", [("payment.card_number", "invalid_card_number")]),
        ("4" * 20, 12, 2030, "123", [("payment.card_number", "invalid_card_number")]),
        (APPROVED, 10, 2026, "123", [("payment.expiry", "card_expired")]),
        (APPROVED, 13, 2030, "123", [("payment.expiry", "invalid_expiry")]),
        (APPROVED, 12, 2030, "12", [("payment.cvc", "invalid_cvc")]),
        (APPROVED, 12, 2030, "12a", [("payment.cvc", "invalid_cvc")]),
        (
            "1234",
            1,
            2020,
            "",
            [
                ("payment.card_number", "invalid_card_number"),
                ("payment.expiry", "card_expired"),
                ("payment.cvc", "invalid_cvc"),
            ],
        ),
    ],
)
def test_a_card_reports_every_problem_without_echoing_the_number(
    number: str, month: int, year: int, cvc: str, expected: list[tuple[str, str]]
) -> None:
    with pytest.raises(DomainValidationError) as error:
        PaymentCard.of(number, month, year, cvc, today=TODAY)

    assert issues_of(error) == expected
    for issue in error.value.issues:
        assert number.replace(" ", "") not in issue.message
        assert number.replace(" ", "") not in str(dict(issue.params))


def test_a_card_expiring_this_month_is_still_accepted() -> None:
    assert card(month=11, year=2026).last4 == "4242"

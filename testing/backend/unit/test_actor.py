from typing import cast

import pytest

from ecommerce.shared_kernel.domain.actor import MAX_ACTOR_LENGTH, Actor
from ecommerce.shared_kernel.domain.errors import DomainValidationError


def codes_for(raw: str) -> list[str]:
    with pytest.raises(DomainValidationError) as raised:
        Actor(raw)
    return [issue.code for issue in raised.value.issues]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Antonio", "Antonio"),
        ("  Maria Silva  ", "Maria Silva"),
        ("Łukasz", "Łukasz"),
        ("李小龍", "李小龍"),
        ("x" * MAX_ACTOR_LENGTH, "x" * MAX_ACTOR_LENGTH),
    ],
)
def test_a_valid_name_is_kept_without_surrounding_spaces(raw: str, expected: str) -> None:
    assert Actor(raw).name == expected


@pytest.mark.parametrize("raw", ["", "   "])
def test_a_missing_name_is_required(raw: str) -> None:
    assert codes_for(raw) == ["required"]


def test_a_name_longer_than_the_limit_is_too_long() -> None:
    with pytest.raises(DomainValidationError) as raised:
        Actor("x" * (MAX_ACTOR_LENGTH + 1))

    issue = raised.value.issues[0]
    assert (issue.field, issue.code, issue.params) == (
        "actor",
        "too_long",
        {"max_length": MAX_ACTOR_LENGTH},
    )


@pytest.mark.parametrize("raw", ["Ann\nSmith", "Ann\tSmith", "Antonio\n", "Ann\x00"])
def test_control_characters_are_not_allowed(raw: str) -> None:
    assert codes_for(raw) == ["control_characters_not_allowed"]


def test_a_name_that_is_not_text_is_a_programming_error() -> None:
    with pytest.raises(TypeError):
        Actor(cast(str, 42))

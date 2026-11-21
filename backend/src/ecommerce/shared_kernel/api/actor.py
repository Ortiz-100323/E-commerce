from dataclasses import replace
from typing import Annotated
from urllib.parse import unquote

from fastapi import Header

from ecommerce.shared_kernel.api.validation import InvalidParameters
from ecommerce.shared_kernel.domain.actor import Actor
from ecommerce.shared_kernel.domain.errors import DomainValidationError, ValidationIssue

ACTOR_HEADER = "X-Actor-Name"
ACTOR_HEADER_DESCRIPTION = (
    "Who is making the change. Required on every change. "
    "Send it percent-encoded as UTF-8 (for example `%C5%81ukasz` for Łukasz); "
    "plain ASCII names can be sent as they are."
)


def require_actor(
    x_actor_name: Annotated[str, Header(alias=ACTOR_HEADER, description=ACTOR_HEADER_DESCRIPTION)],
) -> Actor:
    try:
        name = unquote(x_actor_name, errors="strict")
    except UnicodeDecodeError as error:
        raise InvalidParameters(
            "header",
            [
                ValidationIssue(
                    ACTOR_HEADER,
                    "invalid_encoding",
                    "The name must be percent-encoded UTF-8.",
                )
            ],
        ) from error
    try:
        return Actor(name)
    except DomainValidationError as error:
        raise InvalidParameters(
            "header", (replace(issue, field=ACTOR_HEADER) for issue in error.issues)
        ) from error

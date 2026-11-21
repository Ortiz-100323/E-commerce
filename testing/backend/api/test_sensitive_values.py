import logging

import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from ecommerce.main import create_app
from fakes import dependencies_factory
from problems import problem_client

CARD = "4242424242424242"


class Payment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    card_number: str = Field(pattern=r"^\d{16}$")
    amount: int


def payments_app() -> FastAPI:
    app = create_app(dependencies_factory())

    async def pay(payment: Payment) -> dict[str, int]:
        return {"amount": payment.amount}

    app.add_api_route("/test/payments", pay, methods=["POST"])
    return app


@pytest.mark.parametrize(
    "content",
    [
        f'{{"card_number": "{CARD}", "amount": "ten"}}',
        f'{{"card_number": "{CARD}x", "amount": 10}}',
        f'{{"card_number": "{CARD}", "amount": 10, "cvv": "{CARD}"}}',
        f'{{"amount": {CARD}.5, "card_number": "1"}}',
        f'{{"card_number": "{CARD}",',
    ],
    ids=["wrong-type", "pattern-mismatch", "unknown-field", "card-in-number", "broken-json"],
)
def test_card_numbers_are_never_echoed_in_responses_or_logs(
    content: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    with problem_client(payments_app()) as client:
        response = client.post(
            "/test/payments", content=content, headers={"Content-Type": "application/json"}
        )

    assert response.status_code in (400, 422)
    assert CARD not in response.text
    assert CARD not in caplog.text

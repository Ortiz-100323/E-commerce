from uuid import uuid4

from ecommerce.ordering.application.ports import PaymentResult
from ecommerce.ordering.domain.payment import PaymentCard
from ecommerce.shared_kernel.domain.money import Money

DECLINED_TEST_CARD = "4000000000000002"


class FakePaymentGateway:
    async def charge(self, amount: Money, card: PaymentCard, reference: str) -> PaymentResult:
        if card.number == DECLINED_TEST_CARD:
            return PaymentResult(approved=False, reference="", decline_reason="card_declined")
        return PaymentResult(approved=True, reference=f"fake_{uuid4().hex[:24]}")

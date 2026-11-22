from ecommerce.shared_kernel.domain.errors import DomainError


class IdempotencyKeyReused(DomainError):
    def __init__(self) -> None:
        super().__init__("This Idempotency-Key was already used for a different request.")

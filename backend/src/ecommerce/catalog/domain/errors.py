from ecommerce.shared_kernel.domain.errors import DomainError, DomainValidationError


class InvalidProduct(DomainValidationError):
    pass


class InsufficientStock(DomainError):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        super().__init__(f"{sku}: requested {requested}, available {available}")


class ProductNotSellable(DomainError):
    def __init__(self, sku: str, reason: str) -> None:
        self.sku = sku
        self.reason = reason
        super().__init__(f"{sku} is not sellable: {reason}")

from uuid import UUID

from ecommerce.shared_kernel.domain.errors import DomainError, DomainValidationError, NotFoundError


class InvalidProduct(DomainValidationError):
    pass


class ProductNotFound(NotFoundError):
    def __init__(self, product_id: UUID) -> None:
        self.product_id = product_id
        super().__init__("Product not found.")


class ProductAlreadyExists(DomainError):
    def __init__(self, product_id: UUID) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id} already exists.")


class DuplicateSku(DomainError):
    def __init__(self, sku: str) -> None:
        self.sku = sku
        super().__init__(f"SKU {sku} is already taken.")


class VersionConflict(DomainError):
    def __init__(self, product_id: UUID, *, expected_version: int, current_version: int) -> None:
        self.product_id = product_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"Product {product_id} is at version {current_version}, not {expected_version}."
        )


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

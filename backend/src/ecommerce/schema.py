from ecommerce.catalog.infrastructure.orm import products
from ecommerce.shared_kernel.infrastructure.audit import audit_log
from ecommerce.shared_kernel.infrastructure.database import metadata

TABLES = (audit_log, products)

__all__ = ["TABLES", "metadata"]

from ecommerce.catalog.infrastructure.import_tables import import_batch_rows, import_batches
from ecommerce.catalog.infrastructure.orm import products
from ecommerce.ordering.infrastructure.tables import idempotency_keys, order_lines, orders
from ecommerce.shared_kernel.infrastructure.audit import audit_log
from ecommerce.shared_kernel.infrastructure.database import metadata

TABLES = (
    audit_log,
    products,
    import_batches,
    import_batch_rows,
    orders,
    order_lines,
    idempotency_keys,
)

__all__ = ["TABLES", "metadata"]

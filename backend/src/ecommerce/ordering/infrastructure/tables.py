from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    Uuid,
)

from ecommerce.ordering.domain.value_objects import MAX_EMAIL_LENGTH, MAX_NAME_LENGTH
from ecommerce.shared_kernel.infrastructure.database import metadata

STATUSES = "('PENDING', 'PAID', 'PAYMENT_FAILED')"

orders = Table(
    "orders",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("status", String(16), nullable=False),
    Column("customer_name", String(MAX_NAME_LENGTH), nullable=False),
    Column("customer_email", String(MAX_EMAIL_LENGTH), nullable=False),
    Column("total", Numeric(18, 2), nullable=False),
    Column("payment_reference", String(64), nullable=True),
    Column("card_last4", String(4), nullable=True),
    Column("decline_reason", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("settled_at", DateTime(timezone=True), nullable=True),
    Column("buyer_id", Uuid, nullable=True),
    Index("ix_orders_buyer_created", "buyer_id", "created_at"),
    CheckConstraint(f"status IN {STATUSES}", name="ck_orders_known_status"),
    CheckConstraint("total >= 0", name="ck_orders_total_not_negative"),
    CheckConstraint(
        "card_last4 IS NULL OR card_last4 ~ '^[0-9]{4}$'", name="ck_orders_card_last4_digits"
    ),
    CheckConstraint(
        "(status = 'PENDING') = (settled_at IS NULL)", name="ck_orders_settled_when_final"
    ),
)

order_lines = Table(
    "order_lines",
    metadata,
    Column("order_id", Uuid, ForeignKey("orders.id", name="fk_order_lines_order"), nullable=False),
    Column("sku", String(64), nullable=False),
    Column("product_id", Uuid, nullable=False),
    Column("name", String(MAX_NAME_LENGTH), nullable=False),
    Column("unit_price", Numeric(12, 2), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("gift", Boolean, nullable=False),
    Column("line_total", Numeric(16, 2), nullable=False),
    PrimaryKeyConstraint("order_id", "sku", name="pk_order_lines"),
    CheckConstraint("quantity >= 1", name="ck_order_lines_quantity_positive"),
    CheckConstraint("unit_price >= 0", name="ck_order_lines_price_not_negative"),
    CheckConstraint("line_total = unit_price * quantity", name="ck_order_lines_total_matches"),
)

idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("key", Uuid, primary_key=True),
    Column("endpoint", String(64), nullable=False),
    Column("request_fingerprint", String(67), nullable=False),
    Column(
        "order_id",
        Uuid,
        ForeignKey("orders.id", name="fk_idempotency_keys_order"),
        nullable=True,
    ),
    Column("response_status", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "(order_id IS NULL) = (response_status IS NULL)",
        name="ck_idempotency_keys_outcome_complete",
    ),
)

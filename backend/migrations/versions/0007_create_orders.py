import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=False),
        sa.Column("total", sa.Numeric(16, 2), nullable=False),
        sa.Column("payment_reference", sa.String(64), nullable=True),
        sa.Column("card_last4", sa.String(4), nullable=True),
        sa.Column("decline_reason", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PAID', 'PAYMENT_FAILED')", name="ck_orders_known_status"
        ),
        sa.CheckConstraint("total >= 0", name="ck_orders_total_not_negative"),
        sa.CheckConstraint(
            "card_last4 IS NULL OR card_last4 ~ '^[0-9]{4}$'", name="ck_orders_card_last4_digits"
        ),
        sa.CheckConstraint(
            "(status = 'PENDING') = (settled_at IS NULL)", name="ck_orders_settled_when_final"
        ),
    )
    op.create_table(
        "order_lines",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("gift", sa.Boolean(), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.PrimaryKeyConstraint("order_id", "sku", name="pk_order_lines"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_order_lines_order"),
        sa.CheckConstraint("quantity >= 1", name="ck_order_lines_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_order_lines_price_not_negative"),
        sa.CheckConstraint(
            "line_total = unit_price * quantity", name="ck_order_lines_total_matches"
        ),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Uuid(), primary_key=True),
        sa.Column("endpoint", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_idempotency_keys_order"),
        sa.CheckConstraint(
            "(order_id IS NULL) = (response_status IS NULL)",
            name="ck_idempotency_keys_outcome_complete",
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("order_lines")
    op.drop_table("orders")

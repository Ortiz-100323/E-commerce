from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_orders_created", "orders", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_created", table_name="orders")

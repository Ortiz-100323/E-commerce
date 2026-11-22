import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("buyer_id", sa.Uuid(), nullable=True))
    op.create_index("ix_orders_buyer_created", "orders", ["buyer_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_buyer_created", table_name="orders")
    op.drop_column("orders", "buyer_id")

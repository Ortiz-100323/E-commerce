import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "orders",
        "total",
        existing_type=sa.Numeric(16, 2),
        type_=sa.Numeric(18, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "idempotency_keys",
        "request_fingerprint",
        existing_type=sa.String(64),
        type_=sa.String(67),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "idempotency_keys",
        "request_fingerprint",
        existing_type=sa.String(67),
        type_=sa.String(64),
        existing_nullable=False,
    )
    op.alter_column(
        "orders",
        "total",
        existing_type=sa.Numeric(18, 2),
        type_=sa.Numeric(16, 2),
        existing_nullable=False,
    )

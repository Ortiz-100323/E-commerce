import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SEARCHABLE_COLUMNS = ("name", "sku", "description")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(10, 3), nullable=False),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String(16)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_products_price_not_negative"),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_not_negative"),
        sa.CheckConstraint("weight_kg >= 0", name="ck_products_weight_not_negative"),
        sa.CheckConstraint(
            "price > 0 OR 'GIFT' = ANY(tags)", name="ck_products_zero_price_requires_gift"
        ),
        sa.CheckConstraint("tags <@ ARRAY['GIFT']::varchar[]", name="ck_products_known_tags"),
        sa.CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_products_known_status"),
        sa.CheckConstraint("version >= 1", name="ck_products_version_positive"),
    )
    op.create_index("uq_products_sku", "products", ["sku"], unique=True)
    for column in SEARCHABLE_COLUMNS:
        op.create_index(
            f"ix_products_{column}_trgm",
            "products",
            [column],
            postgresql_using="gin",
            postgresql_ops={column: "gin_trgm_ops"},
        )


def downgrade() -> None:
    for column in SEARCHABLE_COLUMNS:
        op.drop_index(f"ix_products_{column}_trgm", table_name="products")
    op.drop_index("uq_products_sku", table_name="products")
    op.drop_table("products")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")

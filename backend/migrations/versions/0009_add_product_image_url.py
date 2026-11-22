import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(2048), nullable=True))
    op.create_check_constraint(
        "ck_products_image_url_https",
        "products",
        "image_url IS NULL OR image_url LIKE 'https://%'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_products_image_url_https", "products", type_="check")
    op.drop_column("products", "image_url")

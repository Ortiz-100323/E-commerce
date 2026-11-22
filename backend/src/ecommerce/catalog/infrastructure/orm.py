from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY

from ecommerce.shared_kernel.infrastructure.database import metadata

products = Table(
    "products",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("sku", String(64), nullable=False),
    Column("name", String(200), nullable=False),
    Column("description", String(2000), nullable=False),
    Column("category", String(80), nullable=False),
    Column("price", Numeric(12, 2), nullable=False),
    Column("stock", Integer, nullable=False),
    Column("weight_kg", Numeric(10, 3), nullable=False),
    Column("tags", ARRAY(String(16)), nullable=False, server_default=text("'{}'")),
    Column("image_url", String(2048), nullable=True),
    Column("status", String(16), nullable=False),
    Column("version", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("price >= 0", name="ck_products_price_not_negative"),
    CheckConstraint("stock >= 0", name="ck_products_stock_not_negative"),
    CheckConstraint("weight_kg >= 0", name="ck_products_weight_not_negative"),
    CheckConstraint(
        "(price = 0) = ('GIFT' = ANY(tags))", name="ck_products_gift_if_and_only_if_free"
    ),
    CheckConstraint("tags <@ ARRAY['GIFT']::varchar[]", name="ck_products_known_tags"),
    CheckConstraint("status IN ('ACTIVE', 'ARCHIVED')", name="ck_products_known_status"),
    CheckConstraint("version >= 1", name="ck_products_version_positive"),
    CheckConstraint(
        "image_url IS NULL OR image_url LIKE 'https://%'", name="ck_products_image_url_https"
    ),
)

Index("uq_products_sku", products.c.sku, unique=True)

for column in ("name", "sku", "description"):
    Index(
        f"ix_products_{column}_trgm",
        products.c[column],
        postgresql_using="gin",
        postgresql_ops={column: "gin_trgm_ops"},
    )

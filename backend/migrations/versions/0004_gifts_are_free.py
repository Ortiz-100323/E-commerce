from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

OLD_CONSTRAINT = "ck_products_zero_price_requires_gift"
OLD_RULE = "price > 0 OR 'GIFT' = ANY(tags)"
NEW_CONSTRAINT = "ck_products_gift_if_and_only_if_free"
NEW_RULE = "(price = 0) = ('GIFT' = ANY(tags))"

REMOVE_GIFT_FROM_PAID_PRODUCTS = """
WITH fixed AS (
    UPDATE products
    SET tags = array_remove(tags, 'GIFT'),
        version = version + 1,
        updated_at = now()
    WHERE price > 0 AND 'GIFT' = ANY(tags)
    RETURNING id, sku, updated_at
)
INSERT INTO audit_log (occurred_at, actor, event, entity, entity_id, sku, before, after, context)
SELECT
    updated_at,
    'Data migration',
    'product.changed',
    'product',
    id::text,
    sku,
    '{"tags": ["GIFT"]}'::jsonb,
    '{"tags": []}'::jsonb,
    '{"migration": "0004", "reason": "Gifts must be free (D-083)."}'::jsonb
FROM fixed
"""


def upgrade() -> None:
    op.execute(REMOVE_GIFT_FROM_PAID_PRODUCTS)
    op.drop_constraint(OLD_CONSTRAINT, "products", type_="check")
    op.create_check_constraint(NEW_CONSTRAINT, "products", NEW_RULE)


def downgrade() -> None:
    op.drop_constraint(NEW_CONSTRAINT, "products", type_="check")
    op.create_check_constraint(OLD_CONSTRAINT, "products", OLD_RULE)

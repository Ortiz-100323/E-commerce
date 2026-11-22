from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import NullPool

from ecommerce.schema import metadata
from ecommerce.shared_kernel.infrastructure.migrations import alembic_config, upgrade_to_head


def table_names(url: str) -> set[str]:
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return set(inspect(connection).get_table_names())
    finally:
        engine.dispose()


def test_the_migrations_match_the_table_definitions(test_database_url: str) -> None:
    engine = create_engine(test_database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            differences = compare_metadata(context, metadata)
    finally:
        engine.dispose()

    assert differences == []


def test_the_products_migration_downgrades_and_upgrades_cleanly(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    try:
        command.downgrade(config, "0001")
        assert "products" not in table_names(test_database_url)
        assert "weather_searches" in table_names(test_database_url)
    finally:
        upgrade_to_head(test_database_url)

    assert "products" in table_names(test_database_url)


def test_the_audit_log_migration_downgrades_and_upgrades_cleanly(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    try:
        command.downgrade(config, "0002")
        assert "audit_log" not in table_names(test_database_url)
        assert "products" in table_names(test_database_url)
    finally:
        upgrade_to_head(test_database_url)

    assert "audit_log" in table_names(test_database_url)


PAID_GIFT_ID = "00000000-0000-4000-8000-000000000501"
FREE_GIFT_ID = "00000000-0000-4000-8000-000000000502"


def insert_product(url: str, product_id: str, sku: str, price: str, tags: str) -> None:
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO products (id, sku, name, description, category, price, stock, "
                    "weight_kg, tags, status, version, created_at, updated_at) VALUES "
                    "(:id, :sku, 'Shoes', '', 'Sports', :price, 1, 1, CAST(:tags AS varchar[]), "
                    "'ACTIVE', 1, now(), now())"
                ),
                {"id": product_id, "sku": sku, "price": price, "tags": tags},
            )
    finally:
        engine.dispose()


def fetch(url: str, statement: str) -> list[dict[str, object]]:
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(statement)).mappings()]
    finally:
        engine.dispose()


def test_the_gift_migration_removes_the_gift_tag_from_paid_products_and_records_it(
    test_database_url: str,
) -> None:
    clear(test_database_url)
    config = alembic_config(test_database_url)
    try:
        command.downgrade(config, "0003")
        insert_product(test_database_url, PAID_GIFT_ID, "SP-003", "55.00", "{GIFT}")
        insert_product(test_database_url, FREE_GIFT_ID, "GC-001", "0", "{GIFT}")
    finally:
        upgrade_to_head(test_database_url)

    products = fetch(
        test_database_url, "SELECT sku, price, tags, version FROM products ORDER BY sku"
    )
    entries = fetch(
        test_database_url,
        "SELECT actor, event, entity_id, sku, before, after, context FROM audit_log",
    )

    clear(test_database_url)

    assert [(row["sku"], str(row["price"]), row["tags"], row["version"]) for row in products] == [
        ("GC-001", "0.00", ["GIFT"], 1),
        ("SP-003", "55.00", [], 2),
    ]
    assert entries == [
        {
            "actor": "Data migration",
            "event": "product.changed",
            "entity_id": PAID_GIFT_ID,
            "sku": "SP-003",
            "before": {"tags": ["GIFT"]},
            "after": {"tags": []},
            "context": {"migration": "0004", "reason": "Gifts must be free (D-083)."},
        }
    ]


def clear(url: str) -> None:
    engine = create_engine(url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE products, audit_log"))
    finally:
        engine.dispose()


def test_the_weather_migration_drops_the_table_and_can_be_undone(test_database_url: str) -> None:
    config = alembic_config(test_database_url)
    try:
        command.downgrade(config, "0004")
        assert "weather_searches" in table_names(test_database_url)
    finally:
        upgrade_to_head(test_database_url)

    assert "weather_searches" not in table_names(test_database_url)
    assert {"products", "audit_log"} <= table_names(test_database_url)


def test_the_import_batches_migration_downgrades_and_upgrades_cleanly(
    test_database_url: str,
) -> None:
    config = alembic_config(test_database_url)
    try:
        command.downgrade(config, "0005")
        assert {"import_batches", "import_batch_rows"}.isdisjoint(table_names(test_database_url))
        assert "products" in table_names(test_database_url)
    finally:
        upgrade_to_head(test_database_url)

    assert {"import_batches", "import_batch_rows"} <= table_names(test_database_url)

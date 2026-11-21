from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
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

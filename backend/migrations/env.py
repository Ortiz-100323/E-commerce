from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from ecommerce.schema import metadata
from ecommerce.shared_kernel.infrastructure.settings import Settings

database_url = context.config.attributes.get("database_url") or Settings().database_url
engine = create_engine(database_url, poolclass=NullPool)

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()

engine.dispose()

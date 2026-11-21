from sqlalchemy import MetaData, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

metadata = MetaData()

CONNECT_TIMEOUT_SECONDS = 3


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
    )


class SqlAlchemyDatabaseProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def is_up(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (SQLAlchemyError, OSError):
            return False
        return True

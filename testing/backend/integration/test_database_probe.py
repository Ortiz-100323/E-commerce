from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.shared_kernel.infrastructure.database import SqlAlchemyDatabaseProbe, create_engine


async def test_probe_reports_up_when_the_database_answers(engine: AsyncEngine) -> None:
    assert await SqlAlchemyDatabaseProbe(engine).is_up() is True


async def test_probe_reports_down_when_the_database_is_unreachable() -> None:
    engine = create_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none")
    try:
        assert await SqlAlchemyDatabaseProbe(engine).is_up() is False
    finally:
        await engine.dispose()

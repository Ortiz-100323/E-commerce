from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.shared_kernel.infrastructure.database import create_session_factory
from ecommerce.shared_kernel.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
async def probe_table(engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with engine.begin() as connection:
        await connection.execute(
            text("CREATE TABLE IF NOT EXISTS unit_of_work_probe (id integer PRIMARY KEY)")
        )
        await connection.execute(text("TRUNCATE unit_of_work_probe"))
    yield engine
    async with engine.begin() as connection:
        await connection.execute(text("DROP TABLE unit_of_work_probe"))


async def stored_ids(engine: AsyncEngine) -> list[int]:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT id FROM unit_of_work_probe ORDER BY id"))
        return [row[0] for row in result]


async def insert(unit_of_work: SqlAlchemyUnitOfWork, value: int) -> None:
    await unit_of_work.session.execute(
        text("INSERT INTO unit_of_work_probe (id) VALUES (:id)"), {"id": value}
    )


async def test_committed_work_is_stored(probe_table: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(create_session_factory(probe_table)) as unit_of_work:
        await insert(unit_of_work, 1)
        await unit_of_work.commit()

    assert await stored_ids(probe_table) == [1]


async def test_work_that_is_not_committed_is_rolled_back(probe_table: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(create_session_factory(probe_table)) as unit_of_work:
        await insert(unit_of_work, 1)

    assert await stored_ids(probe_table) == []


async def test_an_error_rolls_back_and_propagates(probe_table: AsyncEngine) -> None:
    with pytest.raises(RuntimeError):
        async with SqlAlchemyUnitOfWork(create_session_factory(probe_table)) as unit_of_work:
            await insert(unit_of_work, 1)
            raise RuntimeError("failure")

    assert await stored_ids(probe_table) == []


async def test_explicit_rollback_discards_work(probe_table: AsyncEngine) -> None:
    async with SqlAlchemyUnitOfWork(create_session_factory(probe_table)) as unit_of_work:
        await insert(unit_of_work, 1)
        await unit_of_work.rollback()
        await insert(unit_of_work, 2)
        await unit_of_work.commit()

    assert await stored_ids(probe_table) == [2]


async def test_the_session_is_only_available_inside_the_unit_of_work(
    probe_table: AsyncEngine,
) -> None:
    unit_of_work = SqlAlchemyUnitOfWork(create_session_factory(probe_table))

    with pytest.raises(RuntimeError):
        _ = unit_of_work.session

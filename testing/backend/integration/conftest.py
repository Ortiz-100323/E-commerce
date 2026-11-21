import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.shared_kernel.infrastructure.database import create_engine
from ecommerce.shared_kernel.infrastructure.migrations import upgrade_to_head


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail("TEST_DATABASE_URL is not set. Run the tests through testing/run.py.")
    upgrade_to_head(url)
    return url


@pytest.fixture
async def engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(test_database_url)
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE weather_searches, products"))
    yield engine
    await engine.dispose()

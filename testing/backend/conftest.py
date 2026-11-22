import asyncio
import os
import sys
from collections.abc import AsyncIterator, Callable, Mapping

import pytest
from hypothesis import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.shared_kernel.infrastructure.database import create_engine
from ecommerce.shared_kernel.infrastructure.migrations import upgrade_to_head

settings.register_profile("project", max_examples=200, deadline=None)
settings.load_profile("project")


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    if sys.platform == "win32":
        return {"loop": asyncio.SelectorEventLoop}
    return {"loop": asyncio.new_event_loop}


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
        await connection.execute(
            text("TRUNCATE products, audit_log, import_batch_rows, import_batches")
        )
    yield engine
    await engine.dispose()

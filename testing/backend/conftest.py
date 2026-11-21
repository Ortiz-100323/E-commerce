import asyncio
import sys
from collections.abc import Callable, Mapping

import pytest
from hypothesis import settings

settings.register_profile("project", max_examples=200, deadline=None)
settings.load_profile("project")


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    if sys.platform == "win32":
        return {"loop": asyncio.SelectorEventLoop}
    return {"loop": asyncio.new_event_loop}

import asyncio
import sys
from collections.abc import Callable, Mapping

import pytest


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> Mapping[str, Callable[[], asyncio.AbstractEventLoop]]:
    if sys.platform == "win32":
        return {"loop": asyncio.SelectorEventLoop}
    return {"loop": asyncio.new_event_loop}

import asyncio
import sys
from collections.abc import Callable, Coroutine
from typing import Any


def loop_factory(platform: str | None = None) -> Callable[[], asyncio.AbstractEventLoop] | None:
    chosen = sys.platform if platform is None else platform
    return asyncio.SelectorEventLoop if chosen == "win32" else None


def new_event_loop() -> asyncio.AbstractEventLoop:
    factory = loop_factory()
    return asyncio.new_event_loop() if factory is None else factory()


def run[T](main: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(main, loop_factory=loop_factory())

import asyncio
import sys
from collections.abc import Coroutine
from typing import Any

import pytest
from uvicorn.importer import import_from_string

from ecommerce import event_loop, serve
from ecommerce.identity import seed


def test_windows_gets_the_selector_loop_that_psycopg_needs() -> None:
    assert event_loop.loop_factory("win32") is asyncio.SelectorEventLoop


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_other_platforms_keep_the_default_loop(platform: str) -> None:
    assert event_loop.loop_factory(platform) is None


def test_the_current_platform_is_used_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert event_loop.loop_factory() is asyncio.SelectorEventLoop


def test_a_new_loop_on_windows_is_a_selector_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    loop = event_loop.new_event_loop()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_a_new_loop_elsewhere_is_the_default_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    loop = event_loop.new_event_loop()
    try:
        assert isinstance(loop, asyncio.AbstractEventLoop)
        assert loop.run_until_complete(asyncio.sleep(0, result=7)) == 7
    finally:
        loop.close()


def test_run_finishes_a_coroutine_on_the_compatible_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    async def loop_kind() -> type[asyncio.AbstractEventLoop]:
        return type(asyncio.get_running_loop())

    assert issubclass(event_loop.run(loop_kind()), asyncio.SelectorEventLoop)


def test_the_seed_runs_on_the_compatible_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[str] = []

    async def fake_seed() -> int:
        ran.append("seed")
        return 0

    def fake_run(main: Coroutine[Any, Any, int]) -> int:
        ran.append("compatible loop")
        return asyncio.run(main)

    monkeypatch.setattr(seed, "run", fake_seed)
    monkeypatch.setattr(seed, "run_on_compatible_loop", fake_run)
    monkeypatch.setattr(seed, "configure_logging", lambda level: None)

    assert seed.main() == 0
    assert ran == ["compatible loop", "seed"]


def test_serve_starts_the_production_app_on_the_compatible_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **options: calls.append((app, options)))

    serve.main([])

    assert calls == [
        (
            "ecommerce.main:create_production_app",
            {
                "factory": True,
                "host": "127.0.0.1",
                "port": 8001,
                "access_log": False,
                "loop": "ecommerce.event_loop:new_event_loop",
            },
        )
    ]


def test_serve_takes_another_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **options: calls.append(options))

    serve.main(["--host", "0.0.0.0", "--port", "9000"])

    assert (calls[0]["host"], calls[0]["port"]) == ("0.0.0.0", 9000)


def test_uvicorn_can_load_what_serve_names() -> None:
    assert import_from_string(serve.LOOP) is event_loop.new_event_loop
    assert callable(import_from_string(serve.APP))

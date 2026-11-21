import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

TIMEOUT_SECONDS = 20
SMOKE_CITY = "Lisbon"


class SmokeFailure(Exception):
    pass


def call(method: str, url: str, body: object | None = None) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/html"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def cache_control(url: str) -> str:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return str(response.headers.get("Cache-Control", ""))


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def run(base_url: str) -> int:
    state: dict[str, Any] = {}

    def portal_loads() -> None:
        status, body = call("GET", f"{base_url}/")
        expect(status == 200, f"expected 200, got {status}")
        expect('<div id="root">' in body, "the page has no React root element")

    def page_is_never_stale() -> None:
        for path in ("/", "/admin/products"):
            header = cache_control(f"{base_url}{path}")
            expect(header == "no-cache", f"{path} has Cache-Control {header!r}, expected no-cache")
        _, body = call("GET", f"{base_url}/")
        script = re.search(r'src="(/assets/[^"]+\.js)"', body)
        if script is None:
            raise SmokeFailure("the page loads no script from /assets")
        header = cache_control(f"{base_url}{script.group(1)}")
        expect("immutable" in header, f"the app bundle has Cache-Control {header!r}")

    def health_is_up() -> None:
        status, body = call("GET", f"{base_url}/api/v1/health")
        expect(status == 200, f"expected 200, got {status}: {body}")
        expect(json.loads(body) == {"status": "ok", "database": "up"}, body)

    def real_search_is_saved() -> None:
        status, body = call("POST", f"{base_url}/api/v1/weather/searches", {"city": SMOKE_CITY})
        expect(status == 201, f"expected 201, got {status}: {body}")
        search = json.loads(body)
        expect(search["city"] == SMOKE_CITY, body)
        expect(isinstance(search["temperature_c"], int | float), body)
        state["id"] = search["id"]

    def search_appears_in_history() -> None:
        status, body = call("GET", f"{base_url}/api/v1/weather/searches?limit=5")
        expect(status == 200, f"expected 200, got {status}: {body}")
        history = json.loads(body)
        expect(bool(history) and history[0]["id"] == state.get("id"), body)

    checks: list[tuple[str, Callable[[], None]]] = [
        ("portal loads through nginx", portal_loads),
        ("the page is never served stale", page_is_never_stale),
        ("health check reports the database up", health_is_up),
        (f"real search for {SMOKE_CITY} is saved", real_search_is_saved),
        ("the search is first in the history", search_appears_in_history),
    ]
    for name, check in checks:
        try:
            check()
        except (SmokeFailure, OSError, ValueError, KeyError) as error:
            print(f"FAIL  {name}: {error}")
            return 1
        print(f"PASS  {name}")
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="End-to-end smoke test through the frontend.")
    parser.add_argument("--base-url", required=True)
    arguments = parser.parse_args(argv)
    return run(arguments.base_url.rstrip("/"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

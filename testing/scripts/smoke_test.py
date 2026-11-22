import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from typing import Any

TIMEOUT_SECONDS = 20
SMOKE_SKU = "SMOKE-TEST"
SMOKE_ACTOR = "Smoke test"
SMOKE_PRODUCT = {
    "sku": SMOKE_SKU,
    "name": "Smoke test product",
    "description": "Created by the smoke test. It stays archived between runs.",
    "category": "Smoke tests",
    "price": "1.00",
    "stock": 1,
    "weight_kg": "0.1",
    "gift": False,
}
SMOKE_IDENTITY = (SMOKE_PRODUCT["name"], SMOKE_PRODUCT["description"], SMOKE_PRODUCT["category"])
DECLINED_TEST_CARD = "4000 0000 0000 0002"


SECURITY_HEADERS = {
    "content-security-policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; "
        "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "cross-origin-opener-policy": "same-origin",
}
CSV_HEADER = "name,sku,description,category,price,stock,weight_kg\n"
UPLOAD_ROWS = 9_000
OVERSIZED_BYTES = 7 * 1024 * 1024


def large_csv() -> bytes:
    filler = "x" * 180
    rows = (f"Item {n},UPLOAD-{n},{filler},Misc,1.00,1,0.1\n" for n in range(UPLOAD_ROWS))
    return (CSV_HEADER + "".join(rows)).encode("utf-8")


def missing_headers(headers: dict[str, str]) -> list[str]:
    lowered = {name.lower(): value for name, value in headers.items()}
    return [name for name, expected in SECURITY_HEADERS.items() if lowered.get(name) != expected]


def send_bytes(url: str, body: bytes) -> tuple[int, str, str]:
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "text/csv"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.headers.get("Content-Type", ""), ""
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Content-Type", ""), error.read().decode("utf-8")


def headers_of(url: str) -> dict[str, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return dict(response.headers.items())
    except urllib.error.HTTPError as error:
        return dict(error.headers.items())


def smoke_order() -> dict[str, Any]:
    return {
        "customer": {"name": SMOKE_ACTOR, "email": "smoke-test@example.com"},
        "lines": [{"sku": SMOKE_SKU, "quantity": 1}],
        "payment": {
            "card_number": DECLINED_TEST_CARD,
            "expiry_month": 12,
            "expiry_year": 2099,
            "cvc": "123",
        },
    }


class SmokeFailure(Exception):
    pass


def is_owned_smoke_product(product: dict[str, Any]) -> bool:
    identity = (product.get("name"), product.get("description"), product.get("category"))
    return identity == SMOKE_IDENTITY


def call(
    method: str, url: str, body: object | None = None, headers: dict[str, str] | None = None
) -> tuple[int, str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/html",
            **(headers or {}),
        },
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
    api = f"{base_url}/api/v1"
    actor = {"X-Actor-Name": SMOKE_ACTOR}
    state: dict[str, Any] = {}

    def search(status: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"q": SMOKE_SKU, "status": status})
        code, body = call("GET", f"{api}/products?{query}")
        expect(code == 200, f"search answered {code}: {body}")
        items: list[dict[str, Any]] = json.loads(body)["items"]
        return [item for item in items if item["sku"] == SMOKE_SKU]

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
        status, body = call("GET", f"{api}/health")
        expect(status == 200, f"expected 200, got {status}: {body}")
        expect(json.loads(body) == {"status": "ok", "database": "up"}, body)

    def smoke_product_exists() -> None:
        status, body = call("POST", f"{api}/products", SMOKE_PRODUCT, actor)
        expect(status in (201, 409), f"create answered {status}: {body}")
        if status == 409:
            expect(json.loads(body)["type"].endswith("duplicate-sku"), body)
        found = search("ALL")
        expect(len(found) == 1, f"expected one {SMOKE_SKU}, found {len(found)}")
        expect(
            is_owned_smoke_product(found[0]),
            f"{SMOKE_SKU} belongs to another product; choose a different smoke-test SKU",
        )
        state["id"] = found[0]["id"]

    def restored_product_is_found_by_search() -> None:
        status, body = call("POST", f"{api}/products/{state['id']}/restore", None, actor)
        expect(status == 200, f"restore answered {status}: {body}")
        expect([item["id"] for item in search("ACTIVE")] == [state["id"]], "not found by search")

    def archived_product_leaves_the_shop() -> None:
        status, body = call("DELETE", f"{api}/products/{state['id']}", None, actor)
        expect(status == 200, f"archive answered {status}: {body}")
        expect(search("ACTIVE") == [], f"{SMOKE_SKU} is still in the shop after archiving")

    def checkout_needs_an_idempotency_key() -> None:
        status, body = call("POST", f"{api}/orders", smoke_order())
        expect(status == 400, f"checkout without a key answered {status}: {body}")
        expect(json.loads(body)["type"].endswith("idempotency-key-missing"), body)

    def archived_product_cannot_be_bought() -> None:
        key = {"Idempotency-Key": str(uuid.uuid4())}
        status, body = call("POST", f"{api}/orders", smoke_order(), key)
        expect(status == 409, f"buying an archived product answered {status}: {body}")
        problem = json.loads(body)
        expect(problem["type"].endswith("product-not-sellable"), body)
        expect(problem["items"] == [{"sku": SMOKE_SKU, "reason": "archived"}], body)

    def every_response_carries_the_security_headers() -> None:
        for path in ("/", "/cart", "/api/v1/health", "/api/v1/products/not-a-uuid"):
            missing = missing_headers(headers_of(f"{base_url}{path}"))
            expect(missing == [], f"{path} is missing or has wrong {missing}")

    def a_large_csv_reaches_the_import() -> None:
        body = large_csv()
        status, _, text = send_bytes(f"{api}/imports/preview", body)
        expect(status == 200, f"a {len(body)} byte preview answered {status}: {text[:200]}")

    def an_oversized_upload_gets_a_problem() -> None:
        status, media_type, text = send_bytes(f"{api}/imports/preview", b"x" * OVERSIZED_BYTES)
        expect(status == 413, f"an oversized upload answered {status}")
        expect(media_type.startswith("application/problem+json"), f"413 came as {media_type}")
        expect(json.loads(text)["type"].endswith("payload-too-large"), text)

    checks: list[tuple[str, Callable[[], None]]] = [
        ("portal loads through nginx", portal_loads),
        ("the page is never served stale", page_is_never_stale),
        ("health check reports the database up", health_is_up),
        (f"the {SMOKE_SKU} product exists (created once, then reused)", smoke_product_exists),
        ("a restored product is found by search", restored_product_is_found_by_search),
        ("an archived product leaves the shop", archived_product_leaves_the_shop),
        (
            "checkout refuses a request without an Idempotency-Key",
            checkout_needs_an_idempotency_key,
        ),
        ("an archived product cannot be bought", archived_product_cannot_be_bought),
        (
            "every response carries the security headers",
            every_response_carries_the_security_headers,
        ),
        ("a CSV over 1 MB reaches the import", a_large_csv_reaches_the_import),
        (
            "an oversized upload gets a problem, not an HTML page",
            an_oversized_upload_gets_a_problem,
        ),
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

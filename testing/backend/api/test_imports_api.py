from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from live import ANTONIO, IMPORTS, MARIA, PRODUCTS, live_api, product_body, update_body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from ecommerce.catalog.application.importing import MAX_FILE_BYTES
from fakes import SequenceClock
from problems import assert_problem

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "csv"
SAMPLE = (FIXTURES / "sample-products.csv").read_bytes()
CSV = {"Content-Type": "text/csv"}
HEADER = b"name,sku,description,category,price,stock,weight_kg\n"
STARTED = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
REVIEW_LINES = [7, 25, 41, 47, 50, 52]
RESOLUTIONS: list[tuple[int, dict[str, Any]]] = [
    (7, {"action": "confirm", "expected_outcome": "needs_review"}),
    (25, {"action": "correct", "values": {"name": "Noise Cancelling Headphones"}}),
    (41, {"action": "correct", "values": {"name": "Plain Item"}}),
    (47, {"action": "confirm", "expected_outcome": "needs_review"}),
    (50, {"action": "correct", "values": {"weight_kg": "1.10"}}),
    (52, {"action": "correct", "values": {"category": "Gifts", "weight_kg": "0.01"}}),
]


async def upload(
    client: httpx.AsyncClient, content: bytes = SAMPLE, headers: dict[str, str] | None = None
) -> httpx.Response:
    return await client.post(
        IMPORTS,
        content=content,
        params={"file_name": "products.csv"},
        headers={**CSV, **ANTONIO} if headers is None else headers,
    )


async def resolve(
    client: httpx.AsyncClient, batch_id: str, line: int, body: dict[str, Any]
) -> httpx.Response:
    return await client.patch(f"{IMPORTS}/{batch_id}/rows/{line}", json=body, headers=MARIA)


async def commit(client: httpx.AsyncClient, batch_id: str) -> httpx.Response:
    return await client.post(f"{IMPORTS}/{batch_id}/commit", headers=MARIA)


async def count(engine: AsyncEngine, statement: str) -> int:
    async with engine.connect() as connection:
        return int(await connection.scalar(text(statement)) or 0)


def row(body: dict[str, Any], line: int) -> dict[str, Any]:
    found: dict[str, Any] = next(item for item in body["items"] if item["line"] == line)
    return found


async def test_uploading_keeps_the_import_for_review_and_changes_no_product(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        response = await upload(client)
        body = response.json()
        fetched = await client.get(f"{IMPORTS}/{body['id']}", headers=ANTONIO)

    assert response.status_code == 201, response.text
    assert response.headers["location"] == f"{IMPORTS}/{body['id']}"
    assert body["status"] == "PENDING_REVIEW"
    assert (body["file_name"], body["uploaded_by"], body["rows"]) == ("products.csv", "Antonio", 97)
    assert body["summary"]["create"] == 84
    assert body["pending_lines"] == REVIEW_LINES
    assert body["committable"] is False
    assert fetched.json() == body
    assert row(body, 7)["actions"] == ["confirm", "correct", "skip"]
    assert row(body, 16)["actions"] == []
    assert await count(engine, "SELECT count(*) FROM products") == 0
    assert await count(engine, "SELECT count(*) FROM import_batch_rows") == 97


async def test_the_golden_workflow_imports_90_products_with_6_resolution_entries(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        for line, body in RESOLUTIONS:
            resolved = await resolve(client, batch_id, line, body)
            assert resolved.status_code == 200, resolved.text
        committed = await commit(client, batch_id)

    assert committed.status_code == 200, committed.text
    body = committed.json()
    assert body["status"] == "COMMITTED"
    assert body["result"] == {"created": 90, "updated": 0, "skipped": 0}
    assert await count(engine, "SELECT count(*) FROM products") == 90
    assert await count(engine, "SELECT count(*) FROM audit_log WHERE entity = 'import_row'") == 6
    assert (
        await count(engine, "SELECT count(*) FROM products WHERE 'GIFT' = ANY(tags) AND price = 0")
        == 2
    )


async def test_reimporting_the_same_file_reports_84_unchanged(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        for line, body in RESOLUTIONS:
            await resolve(client, batch_id, line, body)
        await commit(client, batch_id)
        again = await upload(client)

    body = again.json()
    assert body["summary"] == {
        "create": 0,
        "update": 0,
        "unchanged": 84,
        "needs_review": 6,
        "rejected": 2,
        "superseded": 3,
        "blank": 2,
    }
    assert body["file_warnings"] == []


async def test_a_resolved_row_moves_out_of_review(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        response = await resolve(
            client, batch_id, 50, {"action": "correct", "values": {"weight_kg": "1.10"}}
        )

    body = response.json()
    assert body["row"]["outcome"] == "create"
    assert body["row"]["values"]["weight_kg"] == "1.10"
    assert body["row"]["raw_values"]["weight_kg"] == ""
    assert body["row"]["history"][0]["actor"] == "Maria"
    assert body["batch"]["summary"]["needs_review"] == 5
    assert body["batch"]["pending_lines"] == [7, 25, 41, 47, 52]


async def test_commit_is_refused_while_rows_are_pending(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        response = await commit(client, batch_id)

    body = assert_problem(response, 409, "import-not-committable")
    assert body["pending_lines"] == REVIEW_LINES
    assert await count(engine, "SELECT count(*) FROM products") == 0


async def test_rejected_and_superseded_rows_cannot_be_edited(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        rejected = await resolve(
            client, batch_id, 16, {"action": "correct", "values": {"stock": "5"}}
        )
        superseded = await resolve(client, batch_id, 2, {"action": "skip"})

    body = assert_problem(rejected, 409, "import-row-not-resolvable")
    assert (body["line"], body["outcome"], body["action"]) == (16, "rejected", "correct")
    assert assert_problem(superseded, 409, "import-row-not-resolvable")["outcome"] == "superseded"


async def test_an_invalid_correction_is_422_on_the_fields_and_keeps_the_row(
    engine: AsyncEngine,
) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        response = await resolve(
            client,
            batch_id,
            50,
            {"action": "correct", "values": {"weight_kg": "heavy", "stock": "-1"}},
        )
        fetched = await client.get(f"{IMPORTS}/{batch_id}", headers=ANTONIO)

    body = assert_problem(response, 422, "validation-error")
    assert [(error["field"], error["code"]) for error in body["errors"]] == [
        ("stock", "negative_value"),
        ("weight_kg", "invalid_number"),
    ]
    assert row(fetched.json(), 50)["outcome"] == "needs_review"


async def test_values_with_another_action_are_refused(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        response = await resolve(
            client,
            batch_id,
            7,
            {
                "action": "confirm",
                "expected_outcome": "needs_review",
                "values": {"price": "1"},
            },
        )

    body = assert_problem(response, 422, "validation-error")
    assert body["errors"][0]["code"] == "not_allowed"


async def test_a_product_changed_after_the_upload_sends_its_row_back(
    engine: AsyncEngine,
) -> None:
    content = HEADER + b"Running Shoes,RS-001,Lightweight shoes.,Sports,94.99,10,0.8\n"
    async with live_api(engine) as client:
        created = (await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)).json()
        batch_id = (await upload(client, content)).json()["id"]
        await resolve(client, batch_id, 2, {"action": "confirm", "expected_outcome": "update"})
        await client.put(
            f"{PRODUCTS}/{created['id']}",
            json=update_body(created["version"], price="91.00"),
            headers=ANTONIO,
        )
        stale = await commit(client, batch_id)
        fetched = (await client.get(f"{IMPORTS}/{batch_id}", headers=ANTONIO)).json()
        await resolve(client, batch_id, 2, {"action": "confirm", "expected_outcome": "update"})
        retried = await commit(client, batch_id)
        product = (await client.get(f"{PRODUCTS}/{created['id']}")).json()

    body = assert_problem(stale, 409, "import-stale-rows")
    assert body["lines"] == [2]
    again = row(fetched, 2)
    assert again["pending"] is True
    assert again["changes"] == {"price": {"before": "91.00", "after": "94.99"}}
    assert again["issues"][-1]["code"] == "changed_since_preview"
    assert retried.status_code == 200, retried.text
    assert product["price"] == "94.99"


async def test_retrying_a_review_confirmation_does_not_confirm_a_new_update(
    engine: AsyncEngine,
) -> None:
    content = HEADER + b"Running Shoes,RS-001,Lightweight shoes.,Sports,0,10,0.8\n"
    confirmation = {"action": "confirm", "expected_outcome": "needs_review"}
    async with live_api(engine) as client:
        await client.post(PRODUCTS, json=product_body(), headers=ANTONIO)
        batch_id = (await upload(client, content)).json()["id"]
        first = await resolve(client, batch_id, 2, confirmation)
        retry = await resolve(client, batch_id, 2, confirmation)
        fetched = (await client.get(f"{IMPORTS}/{batch_id}", headers=ANTONIO)).json()

    assert first.status_code == retry.status_code == 200
    current = row(fetched, 2)
    assert current["outcome"] == "update"
    assert current["decision"] is None
    assert current["pending"] is True
    assert len(current["history"]) == 1
    assert await count(engine, "SELECT count(*) FROM audit_log WHERE entity = 'import_row'") == 1


async def test_committing_twice_is_a_safe_retry(engine: AsyncEngine) -> None:
    content = HEADER + b"Brand New,NEW-1,Fresh,Misc,5.00,1,0.1\n"
    async with live_api(engine) as client:
        batch_id = (await upload(client, content)).json()["id"]
        first = await commit(client, batch_id)
        second = await commit(client, batch_id)

    assert first.json() == second.json()
    assert await count(engine, "SELECT count(*) FROM products") == 1
    assert (
        await count(engine, "SELECT count(*) FROM audit_log WHERE event = 'import.committed'") == 1
    )


async def test_a_discarded_import_cannot_be_committed(engine: AsyncEngine) -> None:
    content = HEADER + b"Brand New,NEW-1,Fresh,Misc,5.00,1,0.1\n"
    async with live_api(engine) as client:
        batch_id = (await upload(client, content)).json()["id"]
        discarded = await client.delete(f"{IMPORTS}/{batch_id}", headers=MARIA)
        again = await client.delete(f"{IMPORTS}/{batch_id}", headers=MARIA)
        response = await commit(client, batch_id)

    assert discarded.json()["status"] == "DISCARDED"
    assert again.status_code == 200
    assert assert_problem(response, 409, "import-not-pending")["import_status"] == "DISCARDED"
    assert await count(engine, "SELECT count(*) FROM products") == 0


async def test_an_import_expires_after_24_hours(engine: AsyncEngine) -> None:
    clock = SequenceClock(STARTED, STARTED + timedelta(hours=24))
    async with live_api(engine, clock=clock) as client:
        batch_id = (await upload(client)).json()["id"]
        fetched = await client.get(f"{IMPORTS}/{batch_id}", headers=ANTONIO)
        response = await resolve(
            client,
            batch_id,
            7,
            {"action": "confirm", "expected_outcome": "needs_review"},
        )

    assert fetched.json()["status"] == "EXPIRED"
    assert assert_problem(response, 409, "import-not-pending")["import_status"] == "EXPIRED"


async def test_the_same_file_twice_gets_a_warning(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        first = (await upload(client)).json()
        second = (await upload(client)).json()

    [warning] = second["file_warnings"]
    assert warning["code"] == "same_file_already_pending"
    assert warning["params"] == {"batch_id": first["id"]}


async def test_unknown_imports_and_lines_are_404(engine: AsyncEngine) -> None:
    unknown = "00000000-0000-4000-8000-000000000099"
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        missing_import = await client.get(f"{IMPORTS}/{unknown}", headers=ANTONIO)
        missing_line = await resolve(client, batch_id, 999, {"action": "skip"})

    assert_problem(missing_import, 404, "not-found")
    assert_problem(missing_line, 404, "not-found")


async def test_an_upload_needs_an_admin_login_and_a_readable_file(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        anonymous = await upload(client, headers=CSV)
        too_large = await upload(client, HEADER + b"x" * MAX_FILE_BYTES)
        not_csv = await upload(client, headers={"Content-Type": "application/json", **ANTONIO})
        broken = await upload(client, b"name,sku\n")

    assert_problem(anonymous, 401, "authentication-required")
    assert_problem(too_large, 413, "payload-too-large")
    assert_problem(not_csv, 415, "unsupported-media-type")
    assert assert_problem(broken, 422, "validation-error")["errors"][0]["code"] == (
        "missing_columns"
    )
    assert await count(engine, "SELECT count(*) FROM import_batches") == 0


async def test_an_imported_product_history_starts_with_its_csv_line(engine: AsyncEngine) -> None:
    async with live_api(engine) as client:
        batch_id = (await upload(client)).json()["id"]
        for line, body in RESOLUTIONS:
            await resolve(client, batch_id, line, body)
        committed = (await commit(client, batch_id)).json()
        keyboard = next(item for item in committed["items"] if item["line"] == 50)
        search = (await client.get(PRODUCTS, params={"q": "GK-088"})).json()
        history = (
            await client.get(f"{PRODUCTS}/{search['items'][0]['id']}/history", headers=ANTONIO)
        ).json()

    assert keyboard["outcome"] == "create"
    events = [entry["event"] for entry in history["entries"]]
    assert events == ["import.row.corrected", "product.created"]
    assert history["entries"][0]["before"] == {"outcome": "needs_review", "weight_kg": ""}
    assert history["entries"][1]["context"]["raw"].startswith("Gaming Keyboard,GK-088,")
    assert history["entries"][1]["context"]["line"] == 50

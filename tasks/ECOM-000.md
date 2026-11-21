# ECOM-000: Walking skeleton: four containers, weather test feature, local CI

| Field | Value |
|---|---|
| Type | Technical task (environment setup) |
| Phase | 0 |
| Status | **Done** |
| Depends on | — |
| Journal | D-052 to D-060 |

## Context

Before any business rules, we prove that the whole stack works end to end. We use a small weather feature as the test case. **The weather feature is temporary.** It exists only to exercise every layer and container, and it is removed in [ECOM-009](ECOM-009.md) once the catalog takes over that role.

The user flow:
1. I type a city in the React portal.
2. The FastAPI backend looks up the city and its current weather on Open-Meteo, a public API that needs no key.
3. The backend saves the search in PostgreSQL and returns it.
4. The portal shows the result and the search history.

## Scope

**Containers**, all started by `docker compose up --build`:

| Service | Image | Host port | Role |
|---|---|---|---|
| `db` | `postgres:17-alpine` | 5433 | PostgreSQL, with a named volume and a `pg_isready` healthcheck. An init script also creates the `ecommerce_test` database for tests. |
| `backend` | `backend/Dockerfile` (Python 3.13 + uv) | 8001 | FastAPI. Runs `alembic upgrade head`, then uvicorn. Swagger is at `http://localhost:8001/docs`. |
| `frontend` | `frontend/Dockerfile` (Node build, then nginx) | 3000 | Serves the built React app, and proxies `/api/` to `backend:8000`. |
| `ci` | `testing/Dockerfile` (Python 3.13 + uv + Node 22) | — | Runs `python testing/run.py all` once, then exits with its result. Rerun with `docker compose run --rm ci`. |

Host ports 8000 and 8080 are taken by other projects, so we avoid them.

**How the frontend reaches the API (D-054).** The browser only talks to the frontend container. The React code calls relative URLs such as `/api/v1/weather/searches`, and nginx forwards every `/api/` request to `http://backend:8000` over the compose network. The browser sees one origin, so there is no CORS and no API URL baked into the build. When the frontend runs natively (`npm run dev`), Vite's dev-server proxy does the same job.

**Backend**, following the DDD layers (§3.2). `weather` is a temporary bounded context:

| Layer | Contents |
|---|---|
| `weather/domain` | `WeatherSearch` entity, `City` value object (trimmed, 1–100 characters), `WeatherSearchRepository` interface, domain errors |
| `weather/application` | `SearchWeather` and `ListWeatherSearches` use cases, `WeatherProvider` port, DTOs |
| `weather/infrastructure` | `OpenMeteoWeatherProvider` (httpx: geocoding, then current weather), SQLAlchemy imperative mapping, repository |
| `weather/api` | Router and Pydantic schemas |
| `shared_kernel/infrastructure` | Settings (`pydantic-settings`) and the async database engine |
| `shared_kernel/api` | Health router |
| `main.py` | Composition root |

**Endpoints:**

| Method | Path | Result |
|---|---|---|
| GET | `/api/v1/health` | 200 `{"status":"ok","database":"up"}`, or 503 with `"database":"down"` |
| POST | `/api/v1/weather/searches` | Body `{"city":"Lisbon"}`. Returns 201 with the saved search: city, country, latitude, longitude, temperature (°C), wind speed (km/h), weather code and time. Returns 404 if the city is unknown, 422 for an invalid city and 502 if Open-Meteo fails. |
| GET | `/api/v1/weather/searches?limit=10` | The latest searches, newest first |

**Persistence:** one Alembic migration creates the `weather_searches` table. Migrations run when the backend container starts.

**Frontend:** Vite, React 19 and TypeScript (strict). One page with a city form, the latest result and the history list. Plain `fetch`; TanStack Query and React Router arrive in ECOM-006.

**Testing and CI:**
- `testing/run.py`, the single runner (PR-04), with the commands `backend`, `frontend`, `lint`, `nocomments`, `smoke` and `all`.
- `testing/scripts/check_no_comments.py` enforces CC-10 for `.py`, `.ts` and `.tsx` files.
- `import-linter` enforces the layer rules (§8.3).
- `ruff` checks lint and formatting.

**Docs:** a short `README.md` with how to run the project and the CSV download date (2026-11-20).

## Out of scope (moved to later tickets)

- Problem Details error format, mypy strict and Testcontainers: ECOM-001.
- TanStack Query, React Router and the API error class: ECOM-006.
- `profile_csv.py` and `simulate_import.py`: ECOM-010.
- Playwright and GitHub Actions: ECOM-016.

## Acceptance criteria

1. `docker compose up --build` starts `db`, `backend` and `frontend`, and all three become healthy.
2. The `ci` container runs the full suite against the running stack and exits with code 0.
3. At `http://localhost:3000`, I type "Lisbon" and see the current temperature and wind speed. The search appears at the top of the history.
4. The history survives `docker compose down` followed by `docker compose up`, because the data lives in the named volume.
5. At `http://localhost:8001/docs`, I can call `GET /api/v1/health` from Swagger and get 200 with `"database":"up"`.
6. With the `db` container stopped, the health check returns 503.
7. An unknown city shows a clear "city not found" message in the portal.
8. The code follows the DDD layers, and `import-linter` passes.
9. There are no comments in the source or test code, and the check passes.

## Test plan

All tests live in `testing/`. Open-Meteo is mocked everywhere except the smoke test.

| Level | Test |
|---|---|
| Unit: domain | `City` trims input, and rejects empty and over-long names |
| Unit: application | `SearchWeather` with a fake provider and an in-memory repository: saves and returns the search; an unknown city raises `CityNotFound` and saves nothing; a provider failure raises `WeatherUnavailable`. `ListWeatherSearches` returns newest first and respects the limit. |
| Infrastructure | `OpenMeteoWeatherProvider` against `httpx.MockTransport`: maps the geocoding and forecast JSON, handles an empty geocoding result, and handles HTTP 500 and timeouts |
| Integration | The SQLAlchemy repository against the `ecommerce_test` database: saves and lists in order |
| API | Through FastAPI with the provider overridden by a fake: 201, 404, 422 and 502 paths, the history endpoint, and the health endpoint returning 200 or 503 |
| Frontend | Vitest and React Testing Library, specs in `testing/frontend`, with `fetch` stubbed: submitting a city shows the result and refreshes the history; a 404 shows the error message; the history renders on load |
| Smoke (E2E) | `testing/scripts/smoke_test.py`, run by the `ci` container through the frontend's nginx: the portal HTML loads, `/api/v1/health` is up, a real search for "Lisbon" returns 201, and it then appears in the history. This is the only test that calls the real Open-Meteo. |
| Static | ruff, import-linter and the no-comments check |

## Implementation steps

- [x] 1. Repo layout, `.gitignore` and `.dockerignore`
- [x] 2. `testing/run.py` and `check_no_comments.py` (test-first)
- [x] 3. Backend project: uv, FastAPI, settings, health endpoint (test-first)
- [x] 4. Weather domain and application layers with fakes (test-first)
- [x] 5. Open-Meteo provider, persistence and Alembic migration (test-first)
- [x] 6. Weather API endpoints (test-first)
- [x] 7. Frontend page and its tests (test-first)
- [x] 8. Dockerfiles, nginx config and `docker-compose.yml`
- [x] 9. CI container and smoke test
- [x] 10. README, then a full `docker compose up --build` run and a manual check of each criterion

## Verification (2026-11-21)

| # | Criterion | Result |
|---|---|---|
| 1 | Three services healthy | Pass: `db`, `backend` and `frontend` all reported `healthy` |
| 2 | `ci` exits 0 | Pass, on `docker compose up --build` and again on `docker compose run --rm ci`: ruff, import-linter (2 contracts kept), tsc, no comments, 18 tooling tests, 39 backend tests, 6 frontend tests, 4 smoke checks |
| 3 | Search from the portal | Pass through the nginx proxy on port 3000: Porto returned 201 with 15.9 °C and was saved. The page's own behaviour is covered by the Vitest specs; it was not clicked through in a real browser. |
| 4 | History survives a restart | Pass: after `docker compose down` and `up`, the history still held Porto and Lisbon |
| 5 | Health from Swagger | Pass: `/docs` returns 200; `GET /api/v1/health` returns 200 with `"database":"up"` |
| 6 | Health with the database stopped | Pass: 503 with `"database":"down"`, then 200 again once `db` restarted |
| 7 | Unknown city | Pass: the API returns 404 `City not found.`; the portal's message is covered by a Vitest spec |
| 8 | DDD layers | Pass: both import-linter contracts kept |
| 9 | No comments | Pass |

**Known leftovers**
- Starlette 1.10 warns that its `TestClient` should use `httpx2` instead of `httpx`. Installing it was blocked as an unvetted package, so the warning stays until the owner decides.

## Definition of done

- Every acceptance criterion is checked by hand and passes.
- The `ci` container exits with code 0 on a clean `docker compose up --build`.
- Every new behaviour was driven by a failing test first (PR-01).
- The journal and prompt history are updated, and this ticket's status is current.
- The owner has reviewed and accepted it.

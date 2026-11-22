# ADR-0022: Four containers with Docker Compose, and the API on the same origin through nginx

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-11-21 |
| Journal | D-018 (superseded), D-029 (superseded), D-053, D-054, D-084, D-100, D-101 |

## Context

The challenge asks for the solution to run as a Docker container. The first plan was one image serving both the API and the React app. The owner wanted each part in its own container, built and replaced independently, all started with one command.

## Decision

- **`docker compose up` starts four services:**
  - `db`: PostgreSQL 17, a named volume, host port 5433;
  - `backend`: FastAPI on host port 8001. On start it runs the migrations, seeds the first admin, then serves;
  - `frontend`: nginx serving the built React app on host port 3000;
  - `ci`: runs every check once against the running stack, then exits with the result ([ADR-0023](0023-test-first-and-one-runner.md)).
- **The browser only talks to the frontend.**
  - The React code calls relative URLs (`/api/v1/...`), and nginx forwards `/api/` to the backend over the compose network.
  - When running without Docker, Vite's dev server does the same.
- **Hardening in nginx:**
  - a strict Content-Security-Policy, `nosniff`, `no-referrer`, frame denial, a Permissions-Policy and COOP;
  - `server_tokens off`;
  - uploads up to 6 MB, and nginx's own 413 is returned as Problem Details;
  - `no-cache` for the page and long-lived caching for hashed assets, so a reload always gets the new version.
- **No container runs as root,** checked by `run.py containers`. Image sizes are checked by `run.py images`.

## Alternatives discarded

- **One image serving the API and the React app (D-018, D-029):** fewer containers, but the frontend and backend couldn't be built, scaled or replaced separately.
- **The browser calling the backend directly with CORS:** it needs CORS configuration and an API URL baked into the build for each environment.
- **A `ci` service behind a profile:** cleaner, but the owner asked for everything to start with compose.

## Consequences

- No CORS, no per-environment frontend build, and the same relative URLs everywhere.
- The backend's port is published only for Swagger and debugging.
- Ports 3000, 8001 and 5433 must be free.

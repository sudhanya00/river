# River

Anonymous messages dropped into a shared river. Catch one from a stranger; one day yours comes back.
Product rules and build phases live in [HANDOFF.md](HANDOFF.md). [river-prototype.html](river-prototype.html)
is the visual reference.

## Layout

- `backend/` FastAPI + SQLAlchemy + Alembic. All river rules are in `app/river.py`.
  `return_at` and `author_id` never leave the server (see `app/schemas.py`).
- `frontend/` React + Vite + TypeScript PWA, ported from the prototype.
- Postgres 16 on `localhost:54329`, databases `river` and `river_test`, role `river` / password `river`
  (dev only). Either a native install or `docker-compose.yml`.

## Run locally (phase 1, fake auth)

Postgres, one of:

- **Native** (what this machine uses): `winget install PostgreSQL.PostgreSQL.16` with
  `--override "--mode unattended --superpassword <pick one> --serverport 54329"`, then as `postgres`:
  `create role river login password 'river'; create database river owner river; create database river_test owner river;`
- **Docker**: `docker compose up -d db` (creates both databases on first start).

Then:

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
```

```bash
cd backend && .venv/Scripts/alembic upgrade head && .venv/Scripts/python -m app.seed
```

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. In dev, the **Dev** pill in the header switches the fake user
(sent as `X-Dev-User`), makes your drifting messages due, and refills catches. It is not
rendered in production builds, and the backend refuses `/api/dev/*` unless `RIVER_DEV_MODE=true`.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

The DB tests use the `river_test` database and recreate its schema on each run.

## Config

Backend settings are env vars prefixed `RIVER_` (see `app/config.py`): free catches per day,
writes per day, return ranges, cooling period, report threshold, database URL, dev mode.
The content filter wordlist is `backend/app/wordlist.txt`; the client imports the same file.

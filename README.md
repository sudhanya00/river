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

## Run locally

Postgres, one of:

- **Native** (what this machine uses): `winget install PostgreSQL.PostgreSQL.16` with
  `--override "--mode unattended --superpassword <pick one> --serverport 54329"`, then as `postgres`:
  `create role river login password 'river'; create database river owner river; create database river_test owner river;`
- **Docker**: `docker compose up -d db` (creates both databases on first start).

Then copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`
(both gitignored) and fill in the Supabase project URL and anon key. Sign-in is Supabase Auth
(Google and email magic link); Supabase is used for auth only, all river data stays in our Postgres.
Without Supabase values the app falls back to a fake dev user.

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

Open http://localhost:5173. In dev, the **Dev** pill in the header switches to a fake user
(sent as `X-Dev-User`), moves the server clock forward a day / month / year, makes your drifting
messages due, and refills catches. It is not rendered in production builds, and the backend
refuses `X-Dev-User` and `/api/dev/*` unless `RIVER_DEV_MODE=true`.

## Messages from the river (seeds)

Seeds keep the river from running dry. A user catches them only after reading every real message;
they're labelled "From the river" and take no notes (nobody would read them). They live in
`backend/app/seeds.txt`, one paragraph each, and `python -m app.seed` loads new ones (it's
idempotent and refuses the file if any seed fails the length or content checks).

To draft more with Claude Haiku (dev only, needs `ANTHROPIC_API_KEY` or `ant auth login`):

```bash
cd backend && .venv/Scripts/python -m app.generate_seeds 40
```

That writes `backend/seeds/candidates.txt` (gitignored). Read them, copy the keepers into
`app/seeds.txt`, then run `python -m app.seed`. Nothing generated reaches the river unreviewed.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

The DB tests use the `river_test` database and recreate its schema on each run.

## Config

Backend settings are env vars prefixed `RIVER_` (see `app/config.py`): free catches per day,
writes per day, return ranges, cooling period, report threshold, database URL, dev mode.
The content filter wordlist is `backend/app/wordlist.txt`; the client imports the same file.

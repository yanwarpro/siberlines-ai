# SIBERLENS AI

SIBERLENS AI is a defensive social cyber intelligence early-warning prototype. This monorepo contains a React dashboard and a FastAPI service backed by PostgreSQL. It accepts authorized CSV uploads and runs deterministic TF-IDF similarity and hourly-volume analysis. It does not collect social data, call an LLM, or provide authentication.

## Repository layout

```text
backend/
  alembic/                 Database migration environment and revisions
  app/
    api/                   Versioned health endpoint
    core/                  Environment-backed settings
    db/                    SQLAlchemy engine and session
    models/                SQLAlchemy data models
    schemas/               Pydantic read schemas
    services/              Scope notes for deferred processing services
  tests/                   Backend tests
frontend/
  src/
    api/                   Typed HTTP client
    components/            Reusable dashboard components
    pages/                 Overview, dataset, analysis, and alert views
    types/                 API response types
    styles/                Global Tailwind stylesheet
  tests/                   Frontend test plan
data/
  samples/                 Synthetic fixture output (not committed)
docs/                      Proposal, architecture, test plan, demo script
scripts/                   Local development utilities
```

## Requirements

- Python 3.10+
- Node.js 20+
- PostgreSQL 15+

## Local development (Windows PowerShell)

Open two PowerShell terminals in the repository root.

### 1. Configure PostgreSQL and the backend

Create a PostgreSQL database named `siberlens` and replace the `YOUR_USER` / `YOUR_PASSWORD` placeholders in `.env` with the local database credentials (URL-encode reserved characters), or update `DATABASE_URL` to match your local server.

```powershell
Copy-Item .env.example .env
cd backend
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. To run backend tests:

```powershell
pytest
```

### Docker Compose alternative

For a containerized PostgreSQL and API, copy `.env.example` to `.env`, replace all credential placeholders, and run from the repository root:

```powershell
docker compose up --build
```

Compose waits for PostgreSQL, applies migrations, and starts the API. Stop services with `Ctrl+C`, then run `docker compose down`; add `-v` only when intentionally deleting the local PostgreSQL volume and its data.

The Compose stack does not include the frontend container. Run Vite using the frontend commands below.

The health endpoint is `GET http://localhost:8000/api/v1/health`. It reports application liveness and does not claim that PostgreSQL is reachable.

### CSV dataset upload

`POST /api/v1/datasets/upload` accepts a multipart form with a `.csv` `file` and an optional `name`. It creates a UUID dataset and stores post rows in one database transaction. CSV headers must include `timestamp` and `text`; `source_id` and `external_id` are optional. Timestamp values must be ISO 8601. Header matching is case-insensitive and accepts common aliases (`published_at` for timestamp, `content` for text, and `source`/`platform` for source_id). Optional `dataset_label` and `expected_topic` evaluation columns are accepted but ignored. Files are limited to 5 MiB and 10,000 rows. Repeated text is preserved as separate posts; duplicate rows are skipped only when both `source_id` and `external_id` match. The upload is rejected as a whole if a row is invalid; uploading does not automatically run analysis or create alerts.

Example from PowerShell after the API is running:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/datasets/upload `
  -F "file=@.\posts.csv;type=text/csv" `
  -F "name=Authorized sample"
```

The CSV endpoint accepts uploads only from configured CORS origins when called by a browser. CORS is not authentication; do not expose this prototype API publicly for sensitive data without adding an appropriate access-control mechanism.

### Dataset read and database health endpoints

- `GET /api/v1/health/db` executes a lightweight database query and returns HTTP 503 if the database is unavailable.
- `GET /api/v1/datasets?limit=50&offset=0` lists dataset metadata and stored row counts; `limit` is capped at 100.
- `GET /api/v1/datasets/{dataset_id}` returns the same metadata for one UUID dataset, or HTTP 404 when it does not exist.

Dataset read responses deliberately omit descriptions, post text, authors, and raw uploaded rows because these routes do not require authentication. Do not treat this metadata-only design or CORS as access control; add authentication and authorization before using the public API for confidential datasets.

### Persisted dataset analysis

- `POST /api/v1/datasets/{dataset_id}/analyses` calculates and saves a completed run using the selected dataset's stored posts.
- `GET /api/v1/datasets/{dataset_id}/analyses` returns up to 50 saved runs for reopening in the UI.
- `GET /api/v1/analyses/{analysis_id}` returns one saved run and its alert evidence.

Narrative candidates use token-based TF-IDF cosine similarity (threshold `0.24`) and connected components; the displayed sample texts and source/timestamp evidence come from the stored posts. Similarity is bounded to 2,500 posts and 1,000,000 candidate pairs; if those limits are exceeded, the run records a warning and omits similarity groups rather than returning a partial result. Hourly spikes require at least 24 prior hourly bins and 20 baseline posts; a candidate must also exceed the historical mean by three standard deviations and the relative-volume threshold. The backend persists a volume alert only when those checks pass. These heuristics are review signals, not proof of coordination, misinformation, or intent. Evaluation columns such as `dataset_label` and `expected_topic` are not stored or used as model inputs.

Analysis responses include representative raw post text as evidence. The prototype API has no authentication or per-user authorization; do not upload confidential or personally sensitive posts to a publicly reachable deployment.

### 2. Run the frontend

In another terminal, from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Set `VITE_API_BASE_URL` in the frontend environment when the API is hosted somewhere other than `http://localhost:8000/api/v1`. Vite reads its own `.env` files from `frontend/`.

The backend reads `DATABASE_URL` and `CORS_ORIGINS` from the process environment or a root `.env` file. `DATABASE_URL_DOCKER` configures the API container's database connection through the Compose service name. `CORS_ORIGINS` is a comma-separated allowlist of exact origins; wildcard origins are not accepted. The example allows `http://localhost:5173` and `http://127.0.0.1:5173`.

## Database schema

The initial Alembic revision creates:

- `datasets`: UUID source/import metadata, stored row count, and lifecycle status.
- `posts`: UUID dataset-linked records with timestamps, source IDs, text, and content hashes; the latest migration preserves repeated text and deduplicates only matching source/external IDs.
- `analyses`: dataset-linked run status, JSON configuration/metrics, and completion timestamps.
- `alerts`: analysis-linked volume signals with baseline counts and JSON evidence.

For a new database, apply migrations with `alembic upgrade head` from `backend/`. The migrations enable row-level security but do not add policies; use a trusted backend database role with the required table privileges, and do not expose database credentials to the frontend.

The existing Supabase database was created outside Alembic and has no `alembic_version` table. Do not run `alembic upgrade head` against it: that attempts to create tables that already exist. Only after independently verifying that its tables, columns, types, defaults, indexes, constraints, and RLS state match revision `0001_initial`, mark that baseline from `backend/` with `alembic stamp 0001_initial`, then run `alembic upgrade head` to apply later revisions. `stamp` does not apply or validate schema changes. If the schema differs, reconcile it deliberately first. To roll a new database back by one revision, use `alembic downgrade -1`.

## Online deployment

### Backend and PostgreSQL

1. Provision a managed PostgreSQL instance from your hosting provider and create a database/user with least-privilege access.
2. Deploy the `backend/` directory as a Python 3.10+ application. Install with `pip install .` and run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from that directory (adapt the port variable syntax to the provider).
3. Configure `DATABASE_URL` as a secret environment variable using the provider's PostgreSQL connection URL. Use `postgresql+psycopg://` and URL-encode reserved characters in credentials.
4. Configure `CORS_ORIGINS` to the exact deployed frontend origin(s), without a trailing path or wildcard.
5. For a newly provisioned empty database only, run `alembic upgrade head` as a release/pre-deploy command from `backend/` before routing traffic to the new version. For an existing Supabase database, follow the schema verification and stamping guidance above instead.
6. Configure a platform health check to request `/api/v1/health`.

### Frontend

For Netlify, connect the repository root; the checked-in [`netlify.toml`](./netlify.toml) sets the monorepo base to `frontend/`, build command to `npm run build`, publish directory to `dist`, and Node.js version to 20. If entering settings manually in the Netlify UI, use those same values.

1. Configure only frontend variables in Netlify. Set `VITE_API_BASE_URL` to `https://<your-api-host>/api/v1`; this is a public API URL, not a database URL or secret. Remove backend-only variables such as `DATABASE_URL`, `DATABASE_URL_DOCKER`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `CORS_ORIGINS` from the Netlify site/build environment. They belong only in the backend deployment. Trigger a new deploy after changing environment variables.
2. Add the Netlify site's exact origin (for example, `https://<site-name>.netlify.app`) to the backend's `CORS_ORIGINS`, then redeploy/restart the backend. Do not include a path or trailing slash.
3. Check the Netlify deploy log for a successful Vite build and confirm the publish directory is `frontend/dist` (or `dist` relative to the configured `frontend` base).

For other static providers, set the build command to `npm run build` with `frontend/` as the working directory and `dist` as the publish directory.

Never put database credentials or other server secrets in frontend variables; Vite exposes `VITE_` variables to browser code. Use TLS and the hosting provider's secret manager for production settings.

## Checks

The architecture, scope proposal, verification plan, and demo walkthrough are in `docs/`. To write an explicitly synthetic local CSV fixture, run `python scripts/generate_demo_dataset.py` from the repository root. The generated file is ignored by Git and is not loaded by the application.

From `backend/`, run `python -m pytest`. From `frontend/`, run `npm run build` and `npm run lint`. Analytics, data ingestion, and report generation remain unimplemented; their planned service layer is intentionally documented rather than filled with placeholder results.

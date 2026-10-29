# SIBERLENS AI

SIBERLENS AI is a defensive social cyber intelligence early-warning prototype. This repository contains the initial runnable monorepo foundation: a React dashboard shell and a FastAPI service backed by PostgreSQL. It does not collect social data or perform clustering, anomaly detection, LLM analysis, authentication, or analytics.

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

`POST /api/v1/datasets/upload` accepts a multipart form with a `.csv` `file` and an optional `name`. It creates a dataset and posts in one database transaction. CSV headers must include `external_id` and `platform`; optional headers are `text`, `author`, and ISO 8601 `published_at`. Files are limited to 5 MiB and 10,000 rows. The upload is rejected as a whole if a row is invalid; no analysis or alerts are generated.

Example from PowerShell after the API is running:

```powershell
curl.exe -X POST http://localhost:8000/api/v1/datasets/upload `
  -F "file=@.\posts.csv;type=text/csv" `
  -F "name=Authorized sample"
```

The CSV endpoint accepts uploads only from configured CORS origins when called by a browser. CORS is not authentication; do not expose this prototype API publicly for sensitive data without adding an appropriate access-control mechanism.

### Dataset read and database health endpoints

- `GET /api/v1/health/db` executes a lightweight database query and returns HTTP 503 if the database is unavailable.
- `GET /api/v1/datasets?limit=50&offset=0` lists dataset metadata and post counts; `limit` is capped at 100.
- `GET /api/v1/datasets/{dataset_id}` returns the same metadata for one dataset, or HTTP 404 when it does not exist.

Dataset read responses deliberately omit descriptions, post text, authors, and raw uploaded rows because these routes do not require authentication. Do not treat this metadata-only design or CORS as access control; add authentication and authorization before using the public API for confidential datasets.

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

- `datasets`: source/import metadata and lifecycle status.
- `posts`: dataset-linked source records, with a unique external identifier per dataset.
- `analyses`: optional, versioned analysis output associated with a dataset or post. No analysis is generated by this prototype.
- `alerts`: optional alert records associated with a dataset or post. No alerts are generated by this prototype.

Apply migrations with `alembic upgrade head` from `backend/`. To roll the schema back by one revision, use `alembic downgrade -1`.

## Online deployment

### Backend and PostgreSQL

1. Provision a managed PostgreSQL instance from your hosting provider and create a database/user with least-privilege access.
2. Deploy the `backend/` directory as a Python 3.10+ application. Install with `pip install .` and run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from that directory (adapt the port variable syntax to the provider).
3. Configure `DATABASE_URL` as a secret environment variable using the provider's PostgreSQL connection URL. Use `postgresql+psycopg://` and URL-encode reserved characters in credentials.
4. Configure `CORS_ORIGINS` to the exact deployed frontend origin(s), without a trailing path or wildcard.
5. Run `alembic upgrade head` as a release/pre-deploy command from `backend/` before routing traffic to the new version.
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

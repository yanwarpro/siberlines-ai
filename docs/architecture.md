# Architecture

The repository is a single monorepo. `frontend/` contains the React, TypeScript, Vite, Tailwind, and Recharts application. `backend/` contains the FastAPI application, SQLAlchemy models, and Alembic migrations. PostgreSQL is the persistence layer.

The browser calls the versioned API using `VITE_API_BASE_URL`. Backend configuration comes from environment variables, with a root `.env` file supported for local development. CORS is restricted to configured exact origins and GET requests. The health endpoint lives in `backend/app/api/health.py`, reports process liveness only, and does not assert database readiness.

`docker-compose.yml` runs PostgreSQL and the API, waits for PostgreSQL health, and applies Alembic migrations before starting the API. Run the Vite development server separately from `frontend/`.

The initial data model consists of datasets, dataset-linked posts, analyses, and alerts. Analysis and alert records have no generating services at this stage. Planned services are documented under `backend/app/services/` and are intentionally absent until their behavior is specified and tested.

# Architecture

The repository is a single monorepo. `frontend/` contains the React, TypeScript, Vite, Tailwind, and Recharts application. `backend/` contains the FastAPI application, SQLAlchemy models, and Alembic migrations. PostgreSQL is the persistence layer.

The browser calls the versioned API using `VITE_API_BASE_URL`. Backend configuration comes from environment variables, with a root `.env` file supported for local development. CORS is restricted to configured exact origins and GET requests. The health endpoint lives in `backend/app/api/health.py`, reports process liveness only, and does not assert database readiness.

`docker-compose.yml` runs PostgreSQL and the API, waits for PostgreSQL health, and applies Alembic migrations before starting the API. Run the Vite development server separately from `frontend/`.

The data model consists of datasets, dataset-linked posts, analyses, and alerts. `backend/app/services/analysis_service.py` produces analyses from stored posts: token-based TF-IDF cosine similarity groups lexically similar posts, each group is segmented into temporal episodes by a configurable gap, and hourly volume is compared against a historical baseline to raise review signals. Each narrative group also carries cluster-wide keyword evolution and consecutive-episode context comparisons computed from the same stored text. `backend/app/services/csv_service.py` parses and validates uploads. Alert records are produced by the same analysis run; they are review signals, not proof of coordination, misinformation, or intent.

Analysis results are stored as one JSON document in `analyses.metrics_json`, so new derived payloads are additive and do not require a migration. The only schema change introduced for analyst notes is `analyses.notes_json` (revision `0003_analysis_analyst_notes`), which keeps human interpretation separate from automated findings. Services for LLM summarisation, authentication, and report export remain unimplemented and are intentionally absent until their behavior is specified and tested.

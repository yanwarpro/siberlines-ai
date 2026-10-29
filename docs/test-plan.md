# Test plan

## Automated checks

- Backend: run `python -m pytest` from `backend/`. Verify health response shape, database URL environment configuration/validation, and CORS allowlist parsing/validation.
- Migration: run `alembic upgrade head --sql` from `backend/` to verify migration SQL generation without requiring a live PostgreSQL server. Also apply `alembic upgrade head` against a disposable PostgreSQL database before a release.
- Frontend: run `npm run build` and `npm run lint` from `frontend/`; build includes TypeScript project checks.

## Manual checks

1. Start PostgreSQL and the API; request `GET /api/v1/health` and verify `{"status":"ok"}`.
2. Load the dashboard at desktop and mobile widths; verify empty states are shown when no data exists.
3. Configure an allowed frontend origin and verify the browser can call the API; verify an unlisted origin is not allowed.
4. Confirm no secrets, real social data, or generated sample CSVs are committed.

Analytics, ingestion, authorization, retention, and alert behavior need additional requirements and dedicated test cases before implementation.

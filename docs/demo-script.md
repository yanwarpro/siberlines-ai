# Demo script

1. Start PostgreSQL and the API with `docker compose up --build`; start the frontend in a second terminal with `cd frontend`, `npm install`, and `npm run dev`.
2. Open the dashboard and point out that metrics, trends, alerts, and evidence are intentionally empty because no data sources or analytics are configured.
3. Open `http://localhost:8000/docs` and demonstrate `GET /api/v1/health`.
4. Optionally run `python scripts/generate_demo_dataset.py` to create an explicitly synthetic CSV fixture. Explain that the application does not ingest it and it is not real-world intelligence.

Do not present generated placeholders or synthetic examples as actual alerts, evidence, or threat findings.

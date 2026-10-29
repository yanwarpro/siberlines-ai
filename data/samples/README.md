# Samples

No sample records are committed. Run `python scripts/generate_demo_dataset.py` to create a clearly labeled synthetic CSV for development; it is not real intelligence and is not consumed by the application.

Use [`template_posts.csv`](./template_posts.csv) as the upload header template. Add at least one authorized record before upload. Required columns are `external_id` and `platform`; optional columns are `text`, `author`, and `published_at` (ISO 8601, for example `2026-10-29T10:00:00Z`).

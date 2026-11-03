"""Add review workflow columns and deduplication fingerprint to alerts.

Revision ID: 0004_alert_review_workflow
Revises: 0003_analysis_analyst_notes

Why this migration is required:
- `alerts` had no column linking an alert back to its dataset, narrative
  cluster, or temporal episode, so the Alerts page could not present or
  navigate to the originating finding.
- `alerts` had no uniqueness mechanism. Every analysis run inserted a new
  row, so re-running an analysis on the same dataset produced duplicate
  alerts for one finding. `fingerprint` plus a unique index provides the
  database-level guarantee that the API-level check relies on.
- Status changes and analyst notes had nowhere to be stored, so the review
  workflow could not be audited.

All changes are additive. Existing rows are preserved; the new columns are
nullable or carry a server default so legacy alerts stay readable. The
`fingerprint` unique index tolerates NULL so legacy rows can be backfilled
by `scripts/backfill_alert_fingerprints.py` without blocking the migration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_alert_review_workflow"
down_revision = "0003_analysis_analyst_notes"
branch_labels = None
depends_on = None

def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(
        sa.JSON(), "sqlite"
    )

    op.add_column(
        "alerts",
        sa.Column("dataset_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("narrative_cluster_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("episode_id", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("detection_interval_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("detection_interval_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "status_history_json",
            json_type,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "analyst_notes_json",
            json_type,
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_foreign_key(
        "alerts_dataset_id_fkey",
        "alerts",
        "datasets",
        ["dataset_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Legacy rows keep detected_at empty rather than a fabricated value; the
    # backfill script copies created_at where the original detection time is
    # genuinely unknown but the row's own timestamp is a truthful lower bound.
    op.create_index("idx_alerts_status", "alerts", ["status"], unique=False)
    op.create_index("idx_alerts_dataset", "alerts", ["dataset_id"], unique=False)
    op.create_index(
        "idx_alerts_detected_at", "alerts", ["detected_at"], unique=False
    )
    # Postgres and SQLite both treat NULLs as distinct in a unique index, so
    # un-backfilled legacy rows do not collide with each other.
    op.create_index(
        "uq_alerts_fingerprint", "alerts", ["fingerprint"], unique=True
    )

def downgrade() -> None:
    op.drop_index("uq_alerts_fingerprint", table_name="alerts")
    op.drop_index("idx_alerts_detected_at", table_name="alerts")
    op.drop_index("idx_alerts_dataset", table_name="alerts")
    op.drop_index("idx_alerts_status", table_name="alerts")
    op.drop_constraint("alerts_dataset_id_fkey", "alerts", type_="foreignkey")
    op.drop_column("alerts", "updated_at")
    op.drop_column("alerts", "analyst_notes_json")
    op.drop_column("alerts", "status_history_json")
    op.drop_column("alerts", "fingerprint")
    op.drop_column("alerts", "detected_at")
    op.drop_column("alerts", "detection_interval_end")
    op.drop_column("alerts", "detection_interval_start")
    op.drop_column("alerts", "episode_id")
    op.drop_column("alerts", "narrative_cluster_id")
    op.drop_column("alerts", "dataset_id")

"""Persist RSS synchronization runs.

Revision ID: 0006_rss_sync_history
Revises: 0005_rss_feed_management
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_rss_sync_history"
down_revision = "0005_rss_feed_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rss_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_feed_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "total_sources",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "successful_sources",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "failed_sources",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("items_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_articles", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "duplicate_articles",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("invalid_articles", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_feed_id"],
            ["rss_feeds.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_rss_sync_runs_started_at",
        "rss_sync_runs",
        ["started_at"],
    )
    op.create_index(
        "idx_rss_sync_runs_status",
        "rss_sync_runs",
        ["status"],
    )
    op.execute(sa.text("ALTER TABLE rss_sync_runs ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE rss_sync_runs DISABLE ROW LEVEL SECURITY"))
    op.drop_index("idx_rss_sync_runs_status", table_name="rss_sync_runs")
    op.drop_index("idx_rss_sync_runs_started_at", table_name="rss_sync_runs")
    op.drop_table("rss_sync_runs")

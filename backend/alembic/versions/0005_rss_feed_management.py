"""Add user-managed RSS feeds and original source URLs.

Revision ID: 0005_rss_feed_management
Revises: 0004_alert_review_workflow
"""
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_rss_feed_management"
down_revision = "0004_alert_review_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )
    op.create_table(
        "rss_feeds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(length=20), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", name="uq_rss_feeds_dataset_id"),
        sa.UniqueConstraint("url", name="uq_rss_feeds_url"),
    )
    op.create_index("idx_rss_feeds_enabled", "rss_feeds", ["enabled"])

    op.execute(sa.text("ALTER TABLE rss_feeds ENABLE ROW LEVEL SECURITY"))

    datasets = sa.table(
        "datasets",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("row_count", sa.Integer()),
        sa.column("status", sa.String()),
    )
    feeds = sa.table(
        "rss_feeds",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("url", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("dataset_id", postgresql.UUID(as_uuid=True)),
    )
    cisa_dataset_id = UUID("00000000-0000-4000-8000-000000000501")
    ncsc_dataset_id = UUID("00000000-0000-4000-8000-000000000502")
    op.bulk_insert(
        datasets,
        [
            {
                "id": cisa_dataset_id,
                "name": "CISA Cybersecurity Advisories",
                "source_type": "rss_feed",
                "row_count": 0,
                "status": "waiting_for_sync",
            },
            {
                "id": ncsc_dataset_id,
                "name": "UK NCSC Security Updates",
                "source_type": "rss_feed",
                "row_count": 0,
                "status": "waiting_for_sync",
            },
        ],
    )
    op.bulk_insert(
        feeds,
        [
            {
                "id": UUID("00000000-0000-4000-8000-000000000401"),
                "name": "CISA Cybersecurity Advisories",
                "url": "https://www.cisa.gov/cybersecurity-advisories/cybersecurity-advisories.xml",
                "enabled": True,
                "dataset_id": cisa_dataset_id,
            },
            {
                "id": UUID("00000000-0000-4000-8000-000000000402"),
                "name": "UK NCSC Security Updates",
                "url": "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml",
                "enabled": True,
                "dataset_id": ncsc_dataset_id,
            },
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM rss_feeds WHERE id IN "
            "('00000000-0000-4000-8000-000000000401', "
            "'00000000-0000-4000-8000-000000000402')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM datasets WHERE id IN "
            "('00000000-0000-4000-8000-000000000501', "
            "'00000000-0000-4000-8000-000000000502') "
            "AND row_count = 0"
        )
    )
    op.execute(sa.text("ALTER TABLE rss_feeds DISABLE ROW LEVEL SECURITY"))
    op.drop_index("idx_rss_feeds_enabled", table_name="rss_feeds")
    op.drop_table("rss_feeds")
    op.drop_column("posts", "source_url")

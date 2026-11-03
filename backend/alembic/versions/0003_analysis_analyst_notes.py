"""Store analyst notes separately from automated analysis output.

Revision ID: 0003_analysis_analyst_notes
Revises: 0002_preserve_repeated_posts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_analysis_analyst_notes"
down_revision = "0002_preserve_repeated_posts"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "notes_json",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(
                sa.JSON(), "sqlite"
            ),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )

def downgrade() -> None:
    op.drop_column("analyses", "notes_json")

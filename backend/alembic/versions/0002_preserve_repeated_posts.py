"""Allow repeated post text while deduplicating by source identity.

Revision ID: 0002_preserve_repeated_posts
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_preserve_repeated_posts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "posts_dataset_id_content_hash_key",
        "posts",
        type_="unique",
    )
    op.create_index(
        "uq_posts_dataset_source_external_id",
        "posts",
        ["dataset_id", sa.text("coalesce(source_id, '')"), "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_posts_dataset_source_external_id", table_name="posts")
    op.create_unique_constraint(
        "posts_dataset_id_content_hash_key",
        "posts",
        ["dataset_id", "content_hash"],
    )

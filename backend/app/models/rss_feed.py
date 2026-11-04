from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base


class RssSyncRun(Base):
    __tablename__ = "rss_sync_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source_feed_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rss_feeds.id", ondelete="SET NULL"),
    )
    source_name: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_sources: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    successful_sources: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    failed_sources: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    items_received: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    new_articles: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    duplicate_articles: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    invalid_articles: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text)


class RssFeed(Base):
    __tablename__ = "rss_feeds"
    __table_args__ = (
        UniqueConstraint("url", name="uq_rss_feeds_url"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    dataset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        unique=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(20))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    dataset: Mapped["Dataset | None"] = relationship()

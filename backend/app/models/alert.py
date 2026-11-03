from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base

ALERT_STATUSES = (
    "new",
    "pending_review",
    "under_review",
    "resolved",
    "dismissed",
)

ALERT_STATUS_LABELS = {
    "new": "New",
    "pending_review": "Pending Review",
    "under_review": "Under Review",
    "resolved": "Resolved",
    "dismissed": "Dismissed",
}

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    narrative_key: Mapped[str] = mapped_column(String(150), nullable=False)
    narrative_cluster_id: Mapped[str | None] = mapped_column(String(200))
    episode_id: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    baseline_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    observed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    evidence_json: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", server_default="new"
    )
    detection_interval_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    detection_interval_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    status_history_json: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    analyst_notes_json: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    analysis: Mapped["Analysis"] = relationship(back_populates="alerts")

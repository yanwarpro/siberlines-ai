from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id", name="uq_posts_dataset_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(80), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    dataset: Mapped["Dataset"] = relationship(back_populates="posts")
    analyses: Mapped[list["Analysis"]] = relationship(back_populates="post")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="post")

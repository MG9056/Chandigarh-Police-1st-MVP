from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RawRecord(Base):
    __tablename__ = "raw_records"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    run_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crawler_runs.id"),
        nullable=True,
    )

    source_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sources.id"),
        nullable=True,
    )

    case_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    raw_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cleaned_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    language: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    matched_keywords: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    relevance_label: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    relevance_confidence: Mapped[float | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    relevance_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_candidates: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending_mapping",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
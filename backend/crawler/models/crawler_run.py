from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CrawlerRun(Base):
    __tablename__ = "crawler_runs"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
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

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="RUNNING",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    urls_attempted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    urls_skipped_robots: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    records_produced: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    records_relevant: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    error_summary: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    triggered_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
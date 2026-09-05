from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    source_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    poll_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )

    crawl_delay_seconds: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
        default=1.0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    transport_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="direct",
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
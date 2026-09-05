from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RobotsCache(Base):
    __tablename__ = "robots_cache"

    domain: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    allowed_paths_summary: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    ttl_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )
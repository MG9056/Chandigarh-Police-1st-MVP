from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    term: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    is_global: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_by: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
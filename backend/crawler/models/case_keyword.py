from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CaseKeyword(Base):
    __tablename__ = "case_keywords"

    id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    case_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    keyword_id: Mapped[object] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("keywords.id"),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    added_by: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "uq_case_keyword",
            "case_id",
            "keyword_id",
            unique=True,
        ),
    )
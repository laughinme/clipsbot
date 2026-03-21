from datetime import datetime, UTC
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, declarative_mixin


@declarative_mixin
class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

@declarative_mixin
class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        server_onupdate=func.now(),
    )

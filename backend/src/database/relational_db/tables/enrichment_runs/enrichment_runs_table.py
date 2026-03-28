from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..enrichment_jobs import EnrichmentJob
    from ..source_connections import SourceConnection
    from ..sync_runs import SyncRun


class EnrichmentRun(TimestampMixin, Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sync_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", server_default="created", index=True)
    source_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    present_in_latest_sync: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sample_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queued_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    processing_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped["SourceConnection | None"] = relationship("SourceConnection", back_populates="enrichment_runs", lazy="selectin")
    sync_run: Mapped["SyncRun | None"] = relationship("SyncRun", back_populates="enrichment_runs", lazy="selectin")
    enrichment_jobs: Mapped[list["EnrichmentJob"]] = relationship(
        "EnrichmentJob",
        back_populates="enrichment_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

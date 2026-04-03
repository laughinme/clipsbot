from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..enrichment_runs import EnrichmentRun
    from ..corpus_items import CorpusItem
    from ..indexing_jobs import IndexingJob
    from ..source_connections import SourceConnection


class SyncRun(TimestampMixin, Base):
    __tablename__ = "sync_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    coverage_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", server_default="created", index=True)
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_manifest_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sample_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    include_content_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_content_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    new_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unchanged_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    indexed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scan_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped["SourceConnection"] = relationship("SourceConnection", back_populates="sync_runs", lazy="selectin")
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(
        "IndexingJob",
        back_populates="sync_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    last_seen_items: Mapped[list["CorpusItem"]] = relationship(
        "CorpusItem",
        back_populates="last_seen_run",
        lazy="selectin",
    )
    enrichment_runs: Mapped[list["EnrichmentRun"]] = relationship(
        "EnrichmentRun",
        back_populates="sync_run",
        lazy="selectin",
    )

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_projections import CorpusProjection
    from ..sync_runs import SyncRun


class IndexingJob(TimestampMixin, Base):
    __tablename__ = "indexing_jobs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    projection_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("corpus_projections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_kind: Mapped[str] = mapped_column(String(64), nullable=False, default="index_projection", server_default="index_projection")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    projection: Mapped["CorpusProjection"] = relationship("CorpusProjection", back_populates="indexing_jobs", lazy="selectin")
    sync_run: Mapped["SyncRun"] = relationship("SyncRun", back_populates="indexing_jobs", lazy="selectin")

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_items import CorpusItem
    from ..enrichment_runs import EnrichmentRun


class EnrichmentJob(TimestampMixin, Base):
    __tablename__ = "enrichment_jobs"
    __table_args__ = (
        UniqueConstraint("enrichment_run_id", "corpus_item_id", "enrichment_kind", name="uq_enrichment_jobs_run_item_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    enrichment_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("enrichment_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    corpus_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("corpus_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enrichment_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    enrichment_run: Mapped["EnrichmentRun"] = relationship("EnrichmentRun", back_populates="enrichment_jobs", lazy="selectin")
    corpus_item: Mapped["CorpusItem"] = relationship("CorpusItem", lazy="selectin")

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_items import CorpusItem
    from ..indexing_jobs import IndexingJob


class CorpusProjection(TimestampMixin, Base):
    __tablename__ = "corpus_projections"
    __table_args__ = (
        UniqueConstraint("corpus_item_id", "projection_kind", name="uq_corpus_projections_item_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    corpus_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("corpus_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    projection_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending", index=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    corpus_item: Mapped["CorpusItem"] = relationship("CorpusItem", back_populates="projections", lazy="selectin")
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(
        "IndexingJob",
        back_populates="projection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

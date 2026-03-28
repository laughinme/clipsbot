from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_assets import CorpusAsset
    from ..corpus_items import CorpusItem


class CorpusEnrichment(TimestampMixin, Base):
    __tablename__ = "corpus_enrichments"
    __table_args__ = (
        UniqueConstraint("corpus_item_id", "enrichment_kind", name="uq_corpus_enrichments_item_kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    corpus_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("corpus_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("corpus_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    enrichment_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="stub", server_default="stub")
    provider_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    corpus_item: Mapped["CorpusItem"] = relationship("CorpusItem", back_populates="enrichments", lazy="selectin")
    source_asset: Mapped["CorpusAsset | None"] = relationship("CorpusAsset", lazy="selectin")

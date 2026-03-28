from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_assets import CorpusAsset
    from ..corpus_enrichments import CorpusEnrichment
    from ..corpus_projections import CorpusProjection
    from ..source_connections import SourceConnection
    from ..sync_runs import SyncRun


class CorpusItem(TimestampMixin, Base):
    __tablename__ = "corpus_items"
    __table_args__ = (
        UniqueConstraint("source_id", "external_key", name="uq_corpus_items_source_external_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_key: Mapped[str] = mapped_column(String(512), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    author_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    container_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_external_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    present_in_latest_sync: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source: Mapped["SourceConnection"] = relationship("SourceConnection", back_populates="corpus_items", lazy="selectin")
    last_seen_run: Mapped["SyncRun | None"] = relationship("SyncRun", back_populates="last_seen_items", lazy="selectin")
    assets: Mapped[list["CorpusAsset"]] = relationship(
        "CorpusAsset",
        back_populates="corpus_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    projections: Mapped[list["CorpusProjection"]] = relationship(
        "CorpusProjection",
        back_populates="corpus_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    enrichments: Mapped[list["CorpusEnrichment"]] = relationship(
        "CorpusEnrichment",
        back_populates="corpus_item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

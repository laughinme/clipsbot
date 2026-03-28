from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base

if TYPE_CHECKING:
    from ..corpus_items import CorpusItem
    from ..enrichment_runs import EnrichmentRun
    from ..sync_runs import SyncRun


class SourceConnection(TimestampMixin, Base):
    __tablename__ = "source_connections"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active", index=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")

    sync_runs: Mapped[list["SyncRun"]] = relationship(
        "SyncRun",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    corpus_items: Mapped[list["CorpusItem"]] = relationship(
        "CorpusItem",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    enrichment_runs: Mapped[list["EnrichmentRun"]] = relationship(
        "EnrichmentRun",
        back_populates="source",
        lazy="selectin",
    )

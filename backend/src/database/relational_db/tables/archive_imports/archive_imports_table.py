from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base


class TelegramImport(TimestampMixin, Base):
    __tablename__ = "telegram_imports"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    raw_manifest_object_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sample_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    include_message_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_message_types: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    indexed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    messages: Mapped[list["TelegramMessage"]] = relationship(
        "TelegramMessage",
        back_populates="telegram_import",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        "MediaAsset",
        back_populates="telegram_import",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    embedding_jobs: Mapped[list["EmbeddingJob"]] = relationship(
        "EmbeddingJob",
        back_populates="telegram_import",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

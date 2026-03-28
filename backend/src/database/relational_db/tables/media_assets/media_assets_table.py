from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("import_id", "sha256", name="uq_media_assets_import_sha256"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_relative_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    telegram_import: Mapped["TelegramImport"] = relationship("TelegramImport", back_populates="media_assets", lazy="selectin")
    messages: Mapped[list["TelegramMessage"]] = relationship("TelegramMessage", back_populates="media_asset", lazy="selectin")

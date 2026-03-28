from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base


class TelegramMessage(TimestampMixin, Base):
    __tablename__ = "telegram_messages"
    __table_args__ = (
        UniqueConstraint("import_id", "telegram_message_id", name="uq_telegram_messages_import_message"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    import_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("telegram_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    author_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    has_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    media_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending", index=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    telegram_import: Mapped["TelegramImport"] = relationship("TelegramImport", back_populates="messages", lazy="selectin")
    media_asset: Mapped["MediaAsset | None"] = relationship("MediaAsset", back_populates="messages", lazy="selectin")
    embedding_jobs: Mapped[list["EmbeddingJob"]] = relationship(
        "EmbeddingJob",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.clips.schemas import ClipStatus

from ..mixins import TimestampMixin
from ..table_base import Base


class Clip(TimestampMixin, Base):
    __tablename__ = "clips"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ClipStatus.UPLOADING.value)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    uploaded_by: Mapped["User | None"] = relationship("User", back_populates="uploaded_clips", lazy="selectin")
    aliases: Mapped[list["ClipAlias"]] = relationship(
        "ClipAlias",
        back_populates="clip",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ClipAlias(Base):
    __tablename__ = "clip_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clip_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    clip: Mapped[Clip] = relationship("Clip", back_populates="aliases", lazy="selectin")

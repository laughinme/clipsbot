from typing import TYPE_CHECKING
from urllib.parse import quote
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Uuid, String, Boolean, DateTime, Text, Index, Integer

from core.config import get_settings
from ..table_base import Base
from ..mixins import TimestampMixin

if TYPE_CHECKING:
    from ..roles import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), default=uuid4, primary_key=True)
    
    # Credentials
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Minimal profile for template
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    
    # Service
    is_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    __table_args__ = (
        # GIN trigram indexes for fast text search
        Index(
            'users_username_trgm',
            'username',
            postgresql_using='gin',
            postgresql_ops={'username': 'gin_trgm_ops'}
        ),
        Index(
            'users_email_trgm',
            'email',
            postgresql_using='gin',
            postgresql_ops={'email': 'gin_trgm_ops'}
        ),
    )
    
    roles: Mapped[list["Role"]] = relationship(  # pyright: ignore
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )
    
    @property
    def role_slugs(self) -> list[str]:
        return [role.slug for role in self.roles]

    @property
    def avatar_url(self) -> str | None:
        if not self.avatar_key:
            return None

        settings = get_settings()
        encoded_key = quote(self.avatar_key, safe="/")
        return f"{settings.STORAGE_ENDPOINT_PUBLIC}/{settings.STORAGE_PUBLIC_BUCKET}/{encoded_key}"

    def has_roles(self, *slugs: str) -> bool:
        if not slugs:
            return True
        owned = set(self.role_slugs)
        return all(slug in owned for slug in slugs)

    def bump_auth_version(self) -> None:
        self.auth_version = (self.auth_version or 0) + 1

from uuid import UUID, uuid4

from sqlalchemy import (
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..mixins import TimestampMixin
from ..table_base import Base


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, primary_key=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # permissions: Mapped[list["Permission"]] = relationship(
    #     "Permission",
    #     secondary="role_permissions",
    #     back_populates="roles",
    #     lazy="selectin",
    # )
    users: Mapped[list["User"]] = relationship(  # pyright: ignore[reportUndefinedVariable]
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="selectin",
    )


# class Permission(TimestampMixin, Base):
#     __tablename__ = "permissions"

#     id: Mapped[UUID] = mapped_column(
#         Uuid(as_uuid=True), default=uuid4, primary_key=True
#     )
#     slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
#     name: Mapped[str] = mapped_column(String(128), nullable=False)
#     description: Mapped[str | None] = mapped_column(Text, nullable=True)

#     roles: Mapped[list[Role]] = relationship(
#         "Role",
#         secondary="role_permissions",
#         back_populates="permissions",
#         lazy="selectin",
#     )

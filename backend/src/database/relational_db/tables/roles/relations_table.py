from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..table_base import Base


# class RolePermission(Base):
#     __tablename__ = "role_permissions"

#     role_id: Mapped[Uuid] = mapped_column(
#         Uuid(as_uuid=True),
#         ForeignKey("roles.id", ondelete="CASCADE"),
#         primary_key=True,
#     )
#     permission_id: Mapped[Uuid] = mapped_column(
#         Uuid(as_uuid=True),
#         ForeignKey("permissions.id", ondelete="CASCADE"),
#         primary_key=True,
#     )


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[Uuid] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True,
    )
    role_id: Mapped[Uuid] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True, index=True,
    )

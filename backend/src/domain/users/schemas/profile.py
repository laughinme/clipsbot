from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID

from domain.common import TimestampModel


class UserModel(TimestampModel):
    """User account representation."""
    # Configure ORM conversion and drop fields set to their defaults during serialization.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(...)
    telegram_id: int | None = Field(None, description="Telegram user ID")
    telegram_username: str | None = Field(None, description="Telegram username")
    username: str | None = Field(None, description="User's display name")
    avatar_key: str | None = Field(None, description="Storage key of the avatar object")
    avatar_url: str | None = Field(None, description="Public URL of the avatar object")
    banned: bool

    # TODO: Make this field returned only when ?expand=roles
    # Roles list is intentionally optional so it is omitted unless expansion is requested.
    roles: list[str] = Field(
        alias="role_slugs",
        default_factory=list,
        description="User's roles."
    )


class UserPatch(BaseModel):
    username: str | None = Field(None, description="User's display name")


class UserRolesUpdate(BaseModel):
    roles: list[str] = Field(default_factory=list, description="Role slugs to assign")


class UploaderGrantRequest(BaseModel):
    telegram_id: int = Field(..., description="Telegram user ID")
    telegram_username: str | None = Field(None, description="Telegram username without @")
    username: str | None = Field(None, description="Optional display name")

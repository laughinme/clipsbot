from pydantic import BaseModel, Field
from uuid import UUID


class UserShare(BaseModel):
    """
    User schema making possible to share other users public profile data.
    """
    id: UUID = Field(...)
    
    username: str | None = Field(None, description="User's display name")
    avatar_url: str | None = Field(None, description="Public URL of the avatar object")


class UserBrief(BaseModel):
    id: UUID = Field(...)
    username: str | None = Field(None, description="User's display name")
    avatar_url: str | None = Field(None, description="Public URL of the avatar object")

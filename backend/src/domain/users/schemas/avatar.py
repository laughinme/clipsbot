from typing import Literal

from pydantic import BaseModel, Field


class AvatarPresignRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: Literal["image/jpeg", "image/png", "image/webp"]


class AvatarPresignResponse(BaseModel):
    object_key: str = Field(..., min_length=1)
    upload_url: str = Field(..., min_length=1)
    public_url: str = Field(..., min_length=1)
    expires_in: int = Field(..., gt=0)


class AvatarConfirmRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=1024)

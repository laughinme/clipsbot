from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.common import TimestampModel


class ClipStatus(StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ClipModel(TimestampModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    slug: str
    description: str | None = None
    object_key: str | None = None
    bucket: str | None = None
    mime_type: str | None = None
    duration_ms: int | None = None
    size_bytes: int | None = None
    status: ClipStatus
    is_public: bool = True
    uploaded_by_user_id: UUID | None = None
    audio_url: str | None = None
    download_url: str | None = None
    aliases: list[str] = Field(default_factory=list)


class ClipCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool = True
    aliases: list[str] = Field(default_factory=list)


class ClipPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    is_public: bool | None = None
    aliases: list[str] | None = None


class ClipUploadInitRequest(ClipCreate):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=128)


class ClipUploadInitResponse(BaseModel):
    clip: ClipModel
    upload_url: str
    expires_in: int


class ClipFinalizeRequest(BaseModel):
    object_key: str = Field(..., min_length=1)


class ClipSearchResponse(BaseModel):
    items: list[ClipModel]

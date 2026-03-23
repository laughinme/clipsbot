from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.common import TimestampModel


class UploaderInviteModel(TimestampModel):
    id: UUID
    status: str = Field(...)
    invite_link: str = Field(...)
    expires_at: datetime = Field(...)
    revoked_at: datetime | None = Field(None)
    consumed_at: datetime | None = Field(None)
    created_by_user_id: UUID | None = Field(None)
    consumed_by_user_id: UUID | None = Field(None)


class UploaderInviteCreateResponse(UploaderInviteModel):
    pass


class UploaderInviteConsumeRequest(BaseModel):
    invite_token: str = Field(...)
    telegram_id: int = Field(...)
    telegram_username: str | None = Field(None)
    first_name: str | None = Field(None)
    last_name: str | None = Field(None)


class UploaderInviteConsumeResponse(BaseModel):
    invite_token: str = Field(...)
    status: str = Field(...)
    approved_display_name: str | None = Field(None)

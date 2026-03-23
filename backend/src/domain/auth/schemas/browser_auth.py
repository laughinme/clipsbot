from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .tokens import TokenPair


class BrowserAuthStartResponse(BaseModel):
    challenge_token: str = Field(...)
    status: str = Field(...)
    expires_at: datetime = Field(...)
    telegram_deep_link: str = Field(...)
    telegram_bot_username: str = Field(...)


class BrowserAuthStatusResponse(BaseModel):
    challenge_token: str = Field(...)
    status: str = Field(...)
    expires_at: datetime = Field(...)
    approved_at: datetime | None = Field(None)
    approved_telegram_id: int | None = Field(None)
    approved_telegram_username: str | None = Field(None)
    approved_display_name: str | None = Field(None)


class BrowserAuthCompleteRequest(BaseModel):
    challenge_token: str = Field(...)


class BrowserAuthInternalConfirmRequest(BaseModel):
    challenge_token: str = Field(...)
    telegram_id: int = Field(...)
    telegram_username: str | None = Field(None)
    first_name: str | None = Field(None)
    last_name: str | None = Field(None)


class BrowserAuthCompleteResponse(TokenPair):
    pass

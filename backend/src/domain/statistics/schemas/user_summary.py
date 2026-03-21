from datetime import datetime

from pydantic import BaseModel, Field


class UserStatsSummary(BaseModel):
    generated_at: datetime = Field(...)
    total_users: int = Field(..., ge=0)
    onboarded_users: int = Field(..., ge=0)
    banned_users: int = Field(..., ge=0)
    registered_last_24h: int = Field(..., ge=0)

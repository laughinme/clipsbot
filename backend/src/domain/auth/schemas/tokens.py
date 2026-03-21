from pydantic import BaseModel, Field


class TokenPair(BaseModel):
    access_token: str = Field(...)
    refresh_token: str | None = Field(None)


class TokenSet(TokenPair):
    csrf_token: str | None = Field(None)

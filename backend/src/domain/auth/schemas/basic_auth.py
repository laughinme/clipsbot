from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(..., description="Raw Telegram Mini App init data string")

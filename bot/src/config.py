from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_BOT_USERNAME: str = "clips"
    INTERNAL_BACKEND_URL: str = "http://backend:8080/api/v1/internal"
    INTERNAL_BOT_TOKEN: str = "change-me-internal-bot-token"
    WEBAPP_URL: str = "http://localhost/admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]

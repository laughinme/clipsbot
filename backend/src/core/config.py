import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    """
    Project dependencies config
    """
    model_config = SettingsConfigDict(
        env_file=f'{BASE_DIR}/.env',
        extra='ignore'
    )
    
    # Stage / debug
    APP_STAGE: Literal["dev", "prod"] = "dev"
    DEBUG: bool | None = None
    LOG_LEVEL: str = "INFO"
    SQL_ECHO: bool = False
    SCHEDULER_ENABLED: bool = False

    # API settings
    API_PORT: int = 8080
    API_HOST: str = '0.0.0.0'
    
    # Site data (url, paths)
    SITE_URL: str = ''
    
    # Media settings
    MEDIA_DIR: str = 'media'
    MAX_PHOTO_SIZE: int = 5  # in MB
    
    # S3-compatible object storage (MinIO, S3, R2, etc.)
    STORAGE_ENDPOINT_INTERNAL: str = "http://minio:9000"
    STORAGE_ENDPOINT_PUBLIC: str = "http://localhost"
    STORAGE_REGION: str = "us-east-1"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_PUBLIC_BUCKET: str = "media-public"
    STORAGE_PRIVATE_BUCKET: str = "media-private"
    STORAGE_PRESIGN_EXPIRES_SEC: int = 600
    STORAGE_USE_PATH_STYLE: bool = True
    STORAGE_AUTO_CREATE_BUCKETS: bool = True

    # Optional notifications adapter
    NOTIFICATIONS_PROVIDER: Literal["noop", "telegram"] = "noop"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # Auth Settings    
    JWT_PRIVATE_KEY: str | None = None
    JWT_PUBLIC_KEY: str | None = None
    JWT_PRIVATE_KEY_PATH: str | None = None
    JWT_PUBLIC_KEY_PATH: str | None = None
    JWT_ALGO: str = 'RS256'
    ACCESS_TTL: int = 60 * 15
    REFRESH_TTL: int = 60 * 60 * 24 * 7
    CSRF_HMAC_KEY: bytes = b"change-me"

    # Cookie settings
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    COOKIE_PATH: str = "/"

    # CORS settings (optional, use only if you call backend directly)
    CORS_ALLOW_ORIGINS: str = ""
    CORS_ALLOW_ORIGIN_REGEX: str = ""
    
    # Database settings
    DATABASE_URL: str
    REDIS_URL: str

    @field_validator("COOKIE_SAMESITE", mode="before")
    @classmethod
    def _normalize_samesite(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _normalize_debug(cls, value: bool | str | None) -> bool | None:
        if value is None or isinstance(value, bool):
            return value

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        if normalized in {"", "none", "null", "release"}:
            return None

        return value

    @field_validator("CSRF_HMAC_KEY", mode="before")
    @classmethod
    def _ensure_bytes(cls, value: str | bytes) -> bytes:
        if isinstance(value, bytes):
            return value
        return str(value).encode()

    @field_validator("STORAGE_ENDPOINT_INTERNAL", "STORAGE_ENDPOINT_PUBLIC", mode="before")
    @classmethod
    def _normalize_storage_endpoint(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return value.rstrip("/")

    @model_validator(mode="after")
    def _load_jwt_keys(self) -> "Settings":
        if not self.JWT_PRIVATE_KEY and self.JWT_PRIVATE_KEY_PATH:
            private_path = Path(self.JWT_PRIVATE_KEY_PATH)
            if not private_path.is_absolute():
                private_path = BASE_DIR / private_path
            self.JWT_PRIVATE_KEY = private_path.read_text()
        if not self.JWT_PUBLIC_KEY and self.JWT_PUBLIC_KEY_PATH:
            public_path = Path(self.JWT_PUBLIC_KEY_PATH)
            if not public_path.is_absolute():
                public_path = BASE_DIR / public_path
            self.JWT_PUBLIC_KEY = public_path.read_text()
        if not self.JWT_PRIVATE_KEY or not self.JWT_PUBLIC_KEY:
            raise ValueError(
                "JWT keys are required. Provide JWT_PRIVATE_KEY/JWT_PUBLIC_KEY or JWT_*_PATH."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


def clear_settings_cache() -> None:
    get_settings.cache_clear()
    try:
        from service.media import clear_media_storage_service_cache
        clear_media_storage_service_cache()
    except Exception:
        # Media storage service may be unavailable during bootstrap/import phases.
        pass


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s",
    )

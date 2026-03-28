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
    RABBITMQ_ENABLED: bool = True
    WORKER_PREFETCH_COUNT: int = 1
    WORKER_QUEUE_NAMES: str = ""
    TEXT_EMBED_BATCH_SIZE: int = 64
    PHOTO_EMBED_BATCH_SIZE: int = 4
    VOICE_EMBED_BATCH_SIZE: int = 2
    EMBEDDING_REQUEST_CONCURRENCY: int = 4
    EMBEDDING_REQUEST_MAX_RETRIES: int = 3
    EMBEDDING_REQUEST_TIMEOUT_SEC: int = 90
    SUMMARY_REQUEST_TIMEOUT_SEC: int = 90
    OCR_REQUEST_TIMEOUT_SEC: int = 90
    TRANSCRIPT_REQUEST_TIMEOUT_SEC: int = 900
    ARCHIVE_STARTUP_RECOVERY_OLDER_THAN_MINUTES: int = 2
    ARCHIVE_STALE_PROCESSING_MINUTES: int = 30
    ARCHIVE_ENRICHMENT_STALE_PROCESSING_MINUTES: int = 30
    ARCHIVE_AUTO_ENRICH_ON_SYNC: bool = False
    DB_POOL_SIZE: int = 12
    DB_MAX_OVERFLOW: int = 12
    DB_POOL_TIMEOUT_SEC: int = 30

    # API settings
    API_PORT: int = 8080
    API_HOST: str = '0.0.0.0'
    
    # Site data (url, paths)
    SITE_URL: str = ''
    WEBAPP_URL: str = ''
    
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
    STORAGE_CLIPS_BUCKET: str = "clips"
    STORAGE_ARCHIVE_BUCKET: str = "media-private"
    STORAGE_PRESIGN_EXPIRES_SEC: int = 600
    STORAGE_USE_PATH_STYLE: bool = True
    STORAGE_AUTO_CREATE_BUCKETS: bool = True

    # Archive import path mapping
    ARCHIVE_IMPORT_HOST_ROOT: str = ""
    ARCHIVE_IMPORT_CONTAINER_ROOT: str = ""
    ARCHIVE_IMPORT_ALLOWED_ROOTS: str = ""

    # Embeddings / vector search
    EMBEDDING_PROVIDER: Literal["stub", "vertex"] = "stub"
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "global"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-2-preview"
    GEMINI_SUMMARY_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_VECTOR_SIZE: int = 3072
    OCR_PROVIDER: Literal["stub", "vision"] = "stub"
    TRANSCRIPT_PROVIDER: Literal["stub", "speech_v2"] = "stub"
    SUMMARY_PROVIDER: Literal["stub", "vertex"] = "stub"
    GCS_STAGING_BUCKET: str = ""
    GCS_STAGING_PREFIX: str = "archive-staging"
    GCS_STAGING_LOCATION: str = "us-central1"
    GCS_STAGING_AUTO_CREATE_BUCKET: bool = False
    TRANSCRIPT_LANGUAGE_CODES: str = "ru-RU,en-US"
    STT_SHORT_MODEL: str = "latest_short"
    STT_LONG_MODEL: str = "latest_long"
    QDRANT_ENABLED: bool = True
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "knowledge_corpus"
    QDRANT_LOCAL_PATH: str = ""

    # Optional notifications adapter
    NOTIFICATIONS_PROVIDER: Literal["noop", "telegram"] = "noop"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_BOT_USERNAME: str = ""
    TELEGRAM_AUTH_MAX_AGE_SEC: int = 60 * 60 * 24
    UPLOADER_INVITE_TTL_HOURS: int = 72
    INTERNAL_BOT_TOKEN: str = "change-me-internal-bot-token"
    AUTH_DEFAULT_ROLE_SLUG: str = ""
    BOOTSTRAP_ADMIN_TELEGRAM_IDS: str = ""

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
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    RABBITMQ_HEARTBEAT_SEC: int = 600

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

    @field_validator(
        "ARCHIVE_IMPORT_HOST_ROOT",
        "ARCHIVE_IMPORT_CONTAINER_ROOT",
        "ARCHIVE_IMPORT_ALLOWED_ROOTS",
        "QDRANT_URL",
        "QDRANT_LOCAL_PATH",
        "GCS_STAGING_BUCKET",
        "GCS_STAGING_PREFIX",
        mode="before",
    )
    @classmethod
    def _normalize_optional_paths(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip().rstrip("/")

    @field_validator("AUTH_DEFAULT_ROLE_SLUG", mode="before")
    @classmethod
    def _normalize_default_role_slug(cls, value: str | None) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @field_validator("BOOTSTRAP_ADMIN_TELEGRAM_IDS", mode="before")
    @classmethod
    def _normalize_bootstrap_admin_ids(cls, value: str | None) -> str:
        if value is None:
            return ""
        return ",".join(
            part.strip()
            for part in str(value).replace(";", ",").split(",")
            if part.strip()
        )

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
        if not self.WEBAPP_URL and self.SITE_URL:
            self.WEBAPP_URL = f"{self.SITE_URL.rstrip('/')}/admin"
        return self

    @property
    def bootstrap_admin_telegram_ids(self) -> list[int]:
        values: list[int] = []
        for part in self.BOOTSTRAP_ADMIN_TELEGRAM_IDS.split(","):
            candidate = part.strip()
            if not candidate:
                continue
            values.append(int(candidate))
        return values

    @property
    def archive_import_allowed_roots(self) -> list[Path]:
        values: list[Path] = []
        if self.ARCHIVE_IMPORT_ALLOWED_ROOTS:
            parts = self.ARCHIVE_IMPORT_ALLOWED_ROOTS.split(",")
        elif self.ARCHIVE_IMPORT_CONTAINER_ROOT:
            parts = [self.ARCHIVE_IMPORT_CONTAINER_ROOT]
        else:
            parts = []

        for part in parts:
            candidate = str(part).strip()
            if candidate:
                values.append(Path(candidate).expanduser().resolve())
        return values

    @property
    def worker_queue_names(self) -> set[str]:
        return {
            candidate
            for candidate in (part.strip() for part in self.WORKER_QUEUE_NAMES.split(","))
            if candidate
        }

    @property
    def transcript_language_codes(self) -> list[str]:
        return [
            candidate
            for candidate in (part.strip() for part in self.TRANSCRIPT_LANGUAGE_CODES.split(","))
            if candidate
        ]

    @property
    def gcs_staging_bucket_name(self) -> str:
        if self.GCS_STAGING_BUCKET:
            return self.GCS_STAGING_BUCKET
        project = self.GOOGLE_CLOUD_PROJECT.strip().lower().replace("_", "-")
        if not project:
            return ""
        return f"{project}-clipsbot-archive-staging"


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
    try:
        from integrations.embeddings import clear_embedding_provider_cache
        clear_embedding_provider_cache()
    except Exception:
        pass
    try:
        from integrations.qdrant import clear_qdrant_service_cache
        clear_qdrant_service_cache()
    except Exception:
        pass
    try:
        from integrations.gcs_staging import clear_gcs_staging_service_cache
        clear_gcs_staging_service_cache()
    except Exception:
        pass


def configure_logging(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s",
    )

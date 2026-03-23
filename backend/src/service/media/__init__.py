from functools import lru_cache

from core.config import get_settings

from .storage_service import (
    ALLOWED_AVATAR_CONTENT_TYPES,
    ALLOWED_CLIP_CONTENT_TYPES,
    MediaStorageService,
)


@lru_cache
def get_media_storage_service() -> MediaStorageService:
    settings = get_settings()
    return MediaStorageService(
        internal_endpoint=settings.STORAGE_ENDPOINT_INTERNAL,
        public_endpoint=settings.STORAGE_ENDPOINT_PUBLIC,
        region=settings.STORAGE_REGION,
        access_key=settings.STORAGE_ACCESS_KEY,
        secret_key=settings.STORAGE_SECRET_KEY,
        use_path_style=settings.STORAGE_USE_PATH_STYLE,
        presign_expires_sec=settings.STORAGE_PRESIGN_EXPIRES_SEC,
        public_bucket=settings.STORAGE_PUBLIC_BUCKET,
        private_bucket=settings.STORAGE_PRIVATE_BUCKET,
        clips_bucket=settings.STORAGE_CLIPS_BUCKET,
    )


def clear_media_storage_service_cache() -> None:
    get_media_storage_service.cache_clear()

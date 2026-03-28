from __future__ import annotations

import asyncio
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from google.cloud import storage

from core.config import Settings, get_settings


class GcsStagingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT or None)
        self._bucket_checked = False
        self._lock = asyncio.Lock()

    @property
    def bucket_name(self) -> str:
        return self.settings.gcs_staging_bucket_name

    async def ensure_bucket(self) -> str:
        bucket_name = self.bucket_name
        if not bucket_name:
            raise RuntimeError("GCS staging bucket is not configured.")
        if self._bucket_checked:
            return bucket_name

        async with self._lock:
            if self._bucket_checked:
                return bucket_name

            bucket = await asyncio.to_thread(self._client.lookup_bucket, bucket_name)
            if bucket is None:
                if not self.settings.GCS_STAGING_AUTO_CREATE_BUCKET:
                    raise RuntimeError(
                        "GCS staging bucket does not exist. Set GCS_STAGING_BUCKET or enable auto creation."
                    )
                bucket = storage.Bucket(self._client, name=bucket_name)
                await asyncio.to_thread(
                    self._client.create_bucket,
                    bucket,
                    location=self.settings.GCS_STAGING_LOCATION,
                )
            self._bucket_checked = True
            return bucket_name

    def build_object_key(self, *, scope: str, item_key: str, filename: str) -> str:
        safe_scope = scope.strip("/").replace(" ", "-") or "archive"
        safe_item = item_key.replace(":", "/").replace(" ", "-").strip("/") or "item"
        safe_name = Path(filename).name or "payload.bin"
        prefix = self.settings.GCS_STAGING_PREFIX.strip("/")
        if prefix:
            return f"{prefix}/{safe_scope}/{safe_item}/{safe_name}"
        return f"{safe_scope}/{safe_item}/{safe_name}"

    async def upload_bytes(
        self,
        *,
        scope: str,
        item_key: str,
        filename: str,
        payload: bytes,
        content_type: str,
    ) -> str:
        bucket_name = await self.ensure_bucket()
        object_key = self.build_object_key(scope=scope, item_key=item_key, filename=filename)
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(object_key)
        await asyncio.to_thread(
            blob.upload_from_string,
            payload,
            content_type=content_type,
        )
        return f"gs://{bucket_name}/{object_key}"

    async def delete_uri(self, uri: str) -> None:
        parsed = urlparse(uri)
        if parsed.scheme != "gs" or not parsed.netloc:
            return
        bucket = self._client.bucket(parsed.netloc)
        blob = bucket.blob(parsed.path.lstrip("/"))
        await asyncio.to_thread(blob.delete)


@lru_cache
def get_gcs_staging_service() -> GcsStagingService:
    return GcsStagingService(get_settings())


def clear_gcs_staging_service_cache() -> None:
    get_gcs_staging_service.cache_clear()

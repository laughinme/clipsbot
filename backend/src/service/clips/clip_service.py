from __future__ import annotations

import asyncio
import re
from urllib.parse import quote
from uuid import UUID
from uuid import uuid4

from broker import BrokerPublisher
from core.config import get_settings
from database.relational_db import Clip, ClipsInterface, UoW, User, UserInterface
from domain.clips import (
    ClipCreate,
    ClipFinalizeRequest,
    ClipModel,
    ClipPatch,
    ClipSearchResponse,
    ClipStatus,
    ClipUploadInitRequest,
    ClipUploadInitResponse,
)
from service.media import ALLOWED_CLIP_CONTENT_TYPES, MediaStorageService

from .exceptions import ClipNotFoundError, ClipObjectNotFoundError, InvalidClipObjectKeyError, UnsupportedClipContentTypeError


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return normalized or "clip"


class ClipService:
    def __init__(
        self,
        *,
        uow: UoW,
        clip_repo: ClipsInterface,
        user_repo: UserInterface,
        media_storage: MediaStorageService,
        broker: BrokerPublisher,
    ) -> None:
        self.uow = uow
        self.clip_repo = clip_repo
        self.user_repo = user_repo
        self.media_storage = media_storage
        self.broker = broker
        self.settings = get_settings()

    def _build_public_audio_url(self, clip: Clip) -> str | None:
        if not clip.object_key or not clip.bucket:
            return None
        base_url = self.settings.SITE_URL.rstrip("/")
        if not base_url:
            return self.media_storage.build_public_url(bucket=clip.bucket, key=clip.object_key)
        filename = quote(f"{clip.title}.mp3", safe="")
        return f"{base_url}/api/v1/public/clips/{clip.id}/audio/{filename}"

    def _serialize(self, clip: Clip) -> ClipModel:
        aliases = [alias.value for alias in clip.aliases]
        audio_url = None
        download_url = None
        if clip.object_key and clip.bucket:
            audio_url = self._build_public_audio_url(clip)
            download_url = self.media_storage.create_presigned_download_url(bucket=clip.bucket, key=clip.object_key)

        return ClipModel(
            id=clip.id,
            title=clip.title,
            slug=clip.slug,
            description=clip.description,
            object_key=clip.object_key,
            bucket=clip.bucket,
            mime_type=clip.mime_type,
            duration_ms=clip.duration_ms,
            size_bytes=clip.size_bytes,
            status=ClipStatus(clip.status),
            is_public=clip.is_public,
            uploaded_by_user_id=clip.uploaded_by_user_id,
            created_at=clip.created_at,
            updated_at=clip.updated_at,
            aliases=aliases,
            audio_url=audio_url,
            download_url=download_url,
        )

    async def list_public(self, *, search: str | None = None, limit: int = 20) -> ClipSearchResponse:
        clips = await self.clip_repo.list_public(search=search, limit=limit)
        return ClipSearchResponse(items=[self._serialize(clip) for clip in clips])

    async def list_admin(self, *, search: str | None = None, limit: int = 50) -> ClipSearchResponse:
        clips = await self.clip_repo.list_admin(search=search, limit=limit)
        return ClipSearchResponse(items=[self._serialize(clip) for clip in clips])

    async def get_public_by_id(self, clip_id: UUID | str) -> ClipModel:
        clip = await self.clip_repo.get_by_id(clip_id)
        if clip is None or clip.status != ClipStatus.READY.value or not clip.is_public:
            raise ClipNotFoundError()
        return self._serialize(clip)

    async def get_public_audio_payload(self, clip_id: UUID | str) -> tuple[Clip, bytes]:
        clip = await self.clip_repo.get_by_id(clip_id)
        if clip is None or clip.status != ClipStatus.READY.value or not clip.is_public or not clip.object_key or not clip.bucket:
            raise ClipNotFoundError()
        payload = await asyncio.to_thread(
            lambda: self.media_storage.get_object_bytes(bucket=clip.bucket, key=clip.object_key)
        )
        return clip, payload

    async def get_admin_by_id(self, clip_id: UUID | str) -> Clip:
        clip = await self.clip_repo.get_by_id(clip_id)
        if clip is None:
            raise ClipNotFoundError()
        return clip

    async def init_upload(self, payload: ClipUploadInitRequest, uploader: User) -> ClipUploadInitResponse:
        if payload.content_type not in ALLOWED_CLIP_CONTENT_TYPES:
            raise UnsupportedClipContentTypeError(list(ALLOWED_CLIP_CONTENT_TYPES))

        slug_base = _slugify(payload.title)
        clip_id = uuid4()
        clip = Clip(
            id=clip_id,
            title=payload.title,
            slug=f"{slug_base}-{clip_id.hex[:8]}",
            description=payload.description,
            status=ClipStatus.UPLOADING.value,
            is_public=payload.is_public,
            uploaded_by_user_id=uploader.id,
            bucket=self.settings.STORAGE_CLIPS_BUCKET,
        )
        await self.clip_repo.add(clip)
        await self.uow.session.flush()
        await self.clip_repo.replace_aliases(clip, payload.aliases)

        object_key = self.media_storage.build_clip_key(clip.id, payload.filename, payload.content_type)
        clip.object_key = object_key
        clip.mime_type = payload.content_type
        await self.uow.commit()
        await self.uow.session.refresh(clip)

        upload_url = self.media_storage.create_presigned_upload_url(
            bucket=self.settings.STORAGE_CLIPS_BUCKET,
            key=object_key,
            content_type=payload.content_type,
            expires_in=self.settings.STORAGE_PRESIGN_EXPIRES_SEC,
        )
        return ClipUploadInitResponse(
            clip=self._serialize(clip),
            upload_url=upload_url,
            expires_in=self.settings.STORAGE_PRESIGN_EXPIRES_SEC,
        )

    async def finalize_upload(self, clip_id: UUID | str, payload: ClipFinalizeRequest) -> ClipModel:
        clip = await self.get_admin_by_id(clip_id)
        if payload.object_key != clip.object_key or not payload.object_key.startswith(f"clips/{clip.id}/"):
            raise InvalidClipObjectKeyError()

        stat = await asyncio.to_thread(
            lambda: self.media_storage.get_object_stat(
                bucket=self.settings.STORAGE_CLIPS_BUCKET,
                key=payload.object_key,
            )
        )
        if stat is None:
            raise ClipObjectNotFoundError()

        clip.status = ClipStatus.PROCESSING.value
        clip.size_bytes = stat.size_bytes
        clip.mime_type = stat.content_type or clip.mime_type
        await self.uow.commit()
        await self.uow.session.refresh(clip)

        await self.broker.publish_event(
            "clip.uploaded",
            {
                "clip_id": str(clip.id),
                "bucket": self.settings.STORAGE_CLIPS_BUCKET,
                "object_key": clip.object_key,
            },
        )
        return self._serialize(clip)

    async def patch_clip(self, clip_id: UUID | str, payload: ClipPatch) -> ClipModel:
        clip = await self.get_admin_by_id(clip_id)
        data = payload.model_dump(exclude_unset=True)
        aliases = data.pop("aliases", None)
        for field, value in data.items():
            setattr(clip, field, value)
        if payload.title:
            clip.slug = f"{_slugify(payload.title)}-{clip.id.hex[:8]}"
        if aliases is not None:
            await self.clip_repo.replace_aliases(clip, aliases)
        await self.uow.commit()
        await self.uow.session.refresh(clip)
        return self._serialize(clip)

    async def delete_clip(self, clip_id: UUID | str) -> None:
        clip = await self.get_admin_by_id(clip_id)
        if clip.object_key and clip.bucket:
            await asyncio.to_thread(
                lambda: self.media_storage.delete_object(bucket=clip.bucket or self.settings.STORAGE_CLIPS_BUCKET, key=clip.object_key)
            )
        await self.uow.session.delete(clip)
        await self.uow.commit()

    async def search_for_bot(self, *, query: str | None, limit: int = 10) -> ClipSearchResponse:
        clips = await self.clip_repo.search_inline(query, limit=limit)
        return ClipSearchResponse(items=[self._serialize(clip) for clip in clips])

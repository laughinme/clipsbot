from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from broker import ARCHIVE_IMPORT_QUEUE, EMBEDDINGS_QUEUE, BrokerPublisher
from core.config import Settings, get_settings
from core.errors import BadRequestError, NotFoundError
from database.relational_db import (
    EmbeddingJob,
    EmbeddingJobInterface,
    MediaAsset,
    MediaAssetInterface,
    TelegramImport,
    TelegramImportInterface,
    TelegramMessage,
    TelegramMessageInterface,
    UoW,
)
from domain.archive import (
    ArchiveImportCreateRequest,
    ArchiveImportListResponse,
    ArchiveMessageType,
    ArchiveImportModel,
    ArchiveImportStatus,
    ArchiveImportStatusResponse,
    ArchiveIndexStatus,
    EmbeddingJobStatus,
)
from service.media import MediaStorageService

from .parser import parse_message, sha256_file


logger = logging.getLogger(__name__)

SUPPORTED_INDEXABLE_TYPES = {
    "text",
    "photo",
    "voice",
    "video_note",
    "video",
    "audio",
}


class ArchiveImportService:
    def __init__(
        self,
        *,
        uow: UoW,
        import_repo: TelegramImportInterface,
        message_repo: TelegramMessageInterface,
        media_repo: MediaAssetInterface,
        embedding_job_repo: EmbeddingJobInterface,
        media_storage: MediaStorageService,
        broker: BrokerPublisher,
        settings: Settings,
    ) -> None:
        self.uow = uow
        self.import_repo = import_repo
        self.message_repo = message_repo
        self.media_repo = media_repo
        self.embedding_job_repo = embedding_job_repo
        self.media_storage = media_storage
        self.broker = broker
        self.settings = settings

    def _normalize_message_type_filters(self, values: list[ArchiveMessageType]) -> list[str]:
        return sorted({value.value for value in values})

    def _build_import_signature(self, manifest_sha256: str, payload: ArchiveImportCreateRequest) -> str:
        config_payload = {
            "manifest_sha256": manifest_sha256,
            "sample_percent": payload.sample_percent,
            "include_message_types": self._normalize_message_type_filters(payload.include_message_types),
            "exclude_message_types": self._normalize_message_type_filters(payload.exclude_message_types),
        }
        return hashlib.sha256(json.dumps(config_payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _build_source_name(self, base_name: str, payload: ArchiveImportCreateRequest) -> str:
        badges: list[str] = []
        if payload.sample_percent:
            badges.append(f"sample {payload.sample_percent}%")
        if payload.exclude_message_types:
            badges.append("exclude " + ", ".join(self._normalize_message_type_filters(payload.exclude_message_types)))
        if payload.include_message_types:
            badges.append("only " + ", ".join(self._normalize_message_type_filters(payload.include_message_types)))
        if not badges:
            return base_name
        return f"{base_name} · {' · '.join(badges)}"

    def _should_include_by_sample(self, *, chat_id: int | None, telegram_message_id: int, sample_percent: int | None) -> bool:
        if not sample_percent or sample_percent >= 100:
            return True
        bucket_source = f"{chat_id or 'none'}:{telegram_message_id}"
        bucket = int(hashlib.sha256(bucket_source.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < sample_percent

    def _should_include_message(self, parsed, telegram_import: TelegramImport) -> bool:
        include_types = {
            part.strip()
            for part in (telegram_import.include_message_types or "").split(",")
            if part.strip()
        }
        exclude_types = {
            part.strip()
            for part in (telegram_import.exclude_message_types or "").split(",")
            if part.strip()
        }
        if include_types and parsed.message_type.value not in include_types:
            return False
        if exclude_types and parsed.message_type.value in exclude_types:
            return False
        return self._should_include_by_sample(
            chat_id=parsed.chat_id,
            telegram_message_id=parsed.telegram_message_id,
            sample_percent=telegram_import.sample_percent,
        )

    def _normalize_input_path(self, raw_path: str) -> Path:
        requested = Path(raw_path).expanduser()
        if self.settings.ARCHIVE_IMPORT_HOST_ROOT and self.settings.ARCHIVE_IMPORT_CONTAINER_ROOT:
            host_root = Path(self.settings.ARCHIVE_IMPORT_HOST_ROOT).expanduser()
            try:
                relative = requested.resolve().relative_to(host_root.resolve())
                requested = Path(self.settings.ARCHIVE_IMPORT_CONTAINER_ROOT) / relative
            except Exception:
                pass

        resolved = requested.resolve()
        allowed_roots = self.settings.archive_import_allowed_roots
        if allowed_roots and not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise BadRequestError("Archive import path is outside the allowed roots.")
        return resolved

    def _resolve_manifest_path(self, source_path: str) -> tuple[Path, Path]:
        root = self._normalize_input_path(source_path)
        manifest = root / "result.json"
        if root.is_file():
            manifest = root
            root = root.parent
        if not manifest.exists():
            raise BadRequestError(f"Could not find result.json in {source_path}")
        return root, manifest

    async def list_imports(self, *, limit: int = 10) -> ArchiveImportListResponse:
        imports = await self.import_repo.list_recent(limit=limit)
        refreshed: list[ArchiveImportModel] = []
        for telegram_import in imports:
            status = await self.refresh_status(telegram_import.id)
            refreshed_import = await self.import_repo.get_by_id(status.import_id)
            if refreshed_import is not None:
                refreshed.append(ArchiveImportModel.model_validate(refreshed_import))
        return ArchiveImportListResponse(items=refreshed)

    async def start_import(self, payload: ArchiveImportCreateRequest) -> ArchiveImportModel:
        _, manifest_path = self._resolve_manifest_path(payload.source_path)
        manifest_sha256 = await asyncio.to_thread(sha256_file, manifest_path)
        import_signature_sha256 = self._build_import_signature(manifest_sha256, payload)
        existing = await self.import_repo.get_by_manifest_sha256(import_signature_sha256)
        if existing:
            return ArchiveImportModel.model_validate(existing)

        telegram_import = TelegramImport(
            source_name=self._build_source_name(manifest_path.parent.name, payload),
            source_path=payload.source_path,
            manifest_sha256=import_signature_sha256,
            status=ArchiveImportStatus.CREATED.value,
            sample_percent=payload.sample_percent,
            include_message_types=",".join(self._normalize_message_type_filters(payload.include_message_types)) or None,
            exclude_message_types=",".join(self._normalize_message_type_filters(payload.exclude_message_types)) or None,
        )
        await self.import_repo.add(telegram_import)
        await self.uow.commit()
        await self.broker.publish_queue_message(
            ARCHIVE_IMPORT_QUEUE,
            {"import_id": str(telegram_import.id)},
        )
        await self.uow.session.refresh(telegram_import)
        return ArchiveImportModel.model_validate(telegram_import)

    async def get_status(self, import_id) -> ArchiveImportStatusResponse:
        telegram_import = await self.import_repo.get_by_id(import_id)
        if telegram_import is None:
            raise NotFoundError("Archive import not found")
        return await self.refresh_status(telegram_import.id)

    async def refresh_status(self, import_id) -> ArchiveImportStatusResponse:
        telegram_import = await self.import_repo.get_by_id(import_id)
        if telegram_import is None:
            raise NotFoundError("Archive import not found")

        counts = await self.message_repo.count_by_import_and_status(telegram_import.id)
        telegram_import.total_items = await self.message_repo.count_all_by_import(telegram_import.id)
        telegram_import.indexed_items = counts.get(ArchiveIndexStatus.INDEXED.value, 0)
        telegram_import.failed_items = counts.get(ArchiveIndexStatus.FAILED.value, 0)
        telegram_import.skipped_items = counts.get(ArchiveIndexStatus.SKIPPED.value, 0)

        queued_items = counts.get(ArchiveIndexStatus.QUEUED.value, 0)
        processing_items = counts.get(ArchiveIndexStatus.PROCESSING.value, 0)
        terminal_items = telegram_import.indexed_items + telegram_import.failed_items + telegram_import.skipped_items

        if telegram_import.status not in {ArchiveImportStatus.FAILED.value, ArchiveImportStatus.CREATED.value}:
            if telegram_import.total_items and terminal_items >= telegram_import.total_items and queued_items == 0 and processing_items == 0:
                telegram_import.status = ArchiveImportStatus.COMPLETED.value
            else:
                telegram_import.status = ArchiveImportStatus.INDEXING.value

        await self.uow.commit()
        await self.uow.session.refresh(telegram_import)
        progress = 0.0
        if telegram_import.total_items:
            progress = round(terminal_items / telegram_import.total_items, 4)

        return ArchiveImportStatusResponse(
            import_id=telegram_import.id,
            status=telegram_import.status,
            source_name=telegram_import.source_name,
            total_items=telegram_import.total_items,
            queued_items=queued_items,
            processing_items=processing_items,
            indexed_items=telegram_import.indexed_items,
            failed_items=telegram_import.failed_items,
            skipped_items=telegram_import.skipped_items,
            progress=progress,
            created_at=telegram_import.created_at,
            updated_at=telegram_import.updated_at,
        )

    async def process_import(self, import_id) -> None:
        telegram_import = await self.import_repo.get_by_id(import_id)
        if telegram_import is None:
            logger.warning("Archive import %s not found", import_id)
            return
        if telegram_import.status in {
            ArchiveImportStatus.PARSING.value,
            ArchiveImportStatus.INDEXING.value,
            ArchiveImportStatus.COMPLETED.value,
        }:
            return

        root_path, manifest_path = self._resolve_manifest_path(telegram_import.source_path or telegram_import.source_name)
        telegram_import.status = ArchiveImportStatus.PARSING.value
        await self.uow.commit()

        manifest_key = self.media_storage.build_archive_manifest_key(telegram_import.id, manifest_path.name)
        await asyncio.to_thread(
            self.media_storage.put_object_file,
            bucket=self.settings.STORAGE_ARCHIVE_BUCKET,
            key=manifest_key,
            path=manifest_path,
            content_type="application/json",
        )
        telegram_import.raw_manifest_object_key = manifest_key
        await self.uow.commit()

        data = json.loads(manifest_path.read_text())
        messages = data.get("messages", [])
        chat_id = data.get("id")
        chat_title = data.get("name")

        asset_ids_by_sha256: dict[str, str] = {}
        embedding_payloads: list[dict[str, str]] = []

        current_import_id = telegram_import.id
        imported_items_count = 0

        for index, raw_message in enumerate(messages, start=1):
            parsed = parse_message(message=raw_message, chat_id=chat_id, chat_title=chat_title)
            if not self._should_include_message(parsed, telegram_import):
                continue

            media_asset = None
            if parsed.source_relative_path and parsed.media_kind is not None:
                local_path = (root_path / parsed.source_relative_path).resolve()
                if local_path.exists():
                    sha256 = await asyncio.to_thread(sha256_file, local_path)
                    if sha256 in asset_ids_by_sha256:
                        media_asset = await self.media_repo.get_by_id(asset_ids_by_sha256[sha256])
                    else:
                        media_asset = await self.media_repo.get_by_import_and_sha256(telegram_import.id, sha256)

                    if media_asset is None:
                        object_key = self.media_storage.build_archive_media_key(
                            current_import_id,
                            parsed.message_type.value,
                            sha256,
                            parsed.original_filename or local_path.name,
                        )
                        await asyncio.to_thread(
                            self.media_storage.put_object_file,
                            bucket=self.settings.STORAGE_ARCHIVE_BUCKET,
                            key=object_key,
                            path=local_path,
                            content_type=parsed.mime_type,
                        )
                        media_asset = MediaAsset(
                            import_id=current_import_id,
                            storage_bucket=self.settings.STORAGE_ARCHIVE_BUCKET,
                            object_key=object_key,
                            original_filename=parsed.original_filename,
                            source_relative_path=parsed.source_relative_path,
                            mime_type=parsed.mime_type,
                            file_size_bytes=parsed.file_size_bytes,
                            sha256=sha256,
                            duration_ms=parsed.duration_ms,
                            width=parsed.width,
                            height=parsed.height,
                            media_kind=parsed.media_kind.value,
                        )
                        await self.media_repo.add(media_asset)
                        await self.uow.session.flush()
                    asset_ids_by_sha256[sha256] = str(media_asset.id)

            message = TelegramMessage(
                import_id=current_import_id,
                chat_id=parsed.chat_id,
                chat_title=parsed.chat_title,
                telegram_message_id=parsed.telegram_message_id,
                author_telegram_id=parsed.author_telegram_id,
                author_name=parsed.author_name,
                timestamp=parsed.timestamp,
                message_type=parsed.message_type.value,
                text_content=parsed.text_content,
                caption=parsed.caption,
                reply_to_message_id=parsed.reply_to_message_id,
                has_media=parsed.has_media,
                media_asset_id=media_asset.id if media_asset else None,
                index_status=parsed.index_status.value,
                index_error=parsed.index_error,
            )
            await self.message_repo.add(message)
            await self.uow.session.flush()
            imported_items_count += 1

            if parsed.index_status == ArchiveIndexStatus.QUEUED:
                job = EmbeddingJob(
                    import_id=telegram_import.id,
                    message_id=message.id,
                    job_type="embed_message",
                    status=EmbeddingJobStatus.QUEUED.value,
                )
                await self.embedding_job_repo.add(job)
                await self.uow.session.flush()
                embedding_payloads.append(
                    {
                        "job_id": str(job.id),
                        "message_id": str(message.id),
                        "import_id": str(current_import_id),
                    }
                )

            if index % 250 == 0:
                await self.uow.commit()
                self.uow.session.expunge_all()

        telegram_import = await self.import_repo.get_by_id(current_import_id)
        if telegram_import is None:
            raise RuntimeError("Archive import disappeared during processing.")
        telegram_import.total_items = imported_items_count
        telegram_import.status = ArchiveImportStatus.INDEXING.value
        await self.uow.commit()

        chunk_size = 500
        for start in range(0, len(embedding_payloads), chunk_size):
            await self.broker.publish_queue_messages(
                EMBEDDINGS_QUEUE,
                embedding_payloads[start:start + chunk_size],
            )

        await self.refresh_status(current_import_id)

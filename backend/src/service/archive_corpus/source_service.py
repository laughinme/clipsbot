from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from broker import ARCHIVE_INDEX_QUEUE, ARCHIVE_SYNC_QUEUE, BrokerPublisher
from core.config import Settings
from core.errors import BadRequestError, NotFoundError
from database.relational_db import (
    CorpusAsset,
    CorpusAssetInterface,
    CorpusItem,
    CorpusItemInterface,
    CorpusProjection,
    CorpusProjectionInterface,
    IndexingJob,
    IndexingJobInterface,
    SourceConnection,
    SourceConnectionInterface,
    SyncRun,
    SyncRunInterface,
    UoW,
)
from domain.archive import (
    ArchiveContentType,
    CorpusProjectionModel,
    ProjectionIndexStatus,
    SourceConnectionModel,
    SourceCreateRequest,
    SourceListResponse,
    SourceStatus,
    SourceUpdateRequest,
    SourceSyncCreateRequest,
    SyncCoverageKind,
    SyncRunListResponse,
    SyncRunModel,
    SyncRunStatus,
    SyncRunStatusResponse,
)
from service.media import MediaStorageService
from service.archive_imports.parser import sha256_file

from .adapters.base import NormalizedAsset, NormalizedSourceItem, SourceAdapterRegistry
from service.archive_enrichments import ArchiveEnrichmentService


class ArchiveSourceService:
    def __init__(
        self,
        *,
        uow: UoW,
        source_repo: SourceConnectionInterface,
        sync_run_repo: SyncRunInterface,
        corpus_item_repo: CorpusItemInterface,
        corpus_asset_repo: CorpusAssetInterface,
        corpus_projection_repo: CorpusProjectionInterface,
        indexing_job_repo: IndexingJobInterface,
        media_storage: MediaStorageService,
        broker: BrokerPublisher,
        settings: Settings,
        adapter_registry: SourceAdapterRegistry,
        enrichment_service: ArchiveEnrichmentService | None = None,
    ) -> None:
        self.uow = uow
        self.source_repo = source_repo
        self.sync_run_repo = sync_run_repo
        self.corpus_item_repo = corpus_item_repo
        self.corpus_asset_repo = corpus_asset_repo
        self.corpus_projection_repo = corpus_projection_repo
        self.indexing_job_repo = indexing_job_repo
        self.media_storage = media_storage
        self.broker = broker
        self.settings = settings
        self.adapter_registry = adapter_registry
        self.enrichment_service = enrichment_service

    def _get_adapter(self, source_kind: str):
        return self.adapter_registry.get(source_kind)

    def _serialize_content_types(self, values: list[ArchiveContentType]) -> str | None:
        normalized = sorted({value.value for value in values})
        return ",".join(normalized) if normalized else None

    def _deserialize_content_types(self, value: str | None) -> list[ArchiveContentType]:
        return [ArchiveContentType(part.strip()) for part in (value or "").split(",") if part.strip()]

    def _source_model(self, source: SourceConnection) -> SourceConnectionModel:
        return SourceConnectionModel.model_validate(source)

    def _sync_model(
        self,
        sync_run: SyncRun,
        *,
        queued_items: int = 0,
        processing_items: int = 0,
    ) -> SyncRunModel:
        return SyncRunModel(
            id=sync_run.id,
            source_id=sync_run.source_id,
            trigger_kind=sync_run.trigger_kind,
            coverage_kind=sync_run.coverage_kind,
            status=sync_run.status,
            cursor=sync_run.cursor,
            raw_manifest_object_key=sync_run.raw_manifest_object_key,
            sample_percent=sync_run.sample_percent,
            include_content_types=self._deserialize_content_types(sync_run.include_content_types),
            exclude_content_types=self._deserialize_content_types(sync_run.exclude_content_types),
            total_items=sync_run.total_items,
            new_items=sync_run.new_items,
            updated_items=sync_run.updated_items,
            unchanged_items=sync_run.unchanged_items,
            indexed_items=sync_run.indexed_items,
            failed_items=sync_run.failed_items,
            skipped_items=sync_run.skipped_items,
            queued_items=queued_items,
            processing_items=processing_items,
            started_at=sync_run.started_at,
            completed_at=sync_run.completed_at,
            created_at=sync_run.created_at,
            updated_at=sync_run.updated_at,
        )

    async def create_source(self, payload: SourceCreateRequest) -> SourceConnectionModel:
        adapter = self._get_adapter(payload.kind.value)
        adapter.validate_source_config(payload.config_json)
        existing = await self.source_repo.get_by_slug(payload.slug)
        if existing is not None:
            raise BadRequestError("Source slug already exists.")

        source = SourceConnection(
            kind=payload.kind.value,
            slug=payload.slug,
            display_name=payload.display_name,
            status=SourceStatus.ACTIVE.value,
            config_json=payload.config_json,
        )
        await self.source_repo.add(source)
        await self.uow.commit()
        await self.uow.session.refresh(source)
        return self._source_model(source)

    async def update_source(self, source_id: UUID | str, payload: SourceUpdateRequest) -> SourceConnectionModel:
        source = await self.source_repo.get_by_id(source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")

        if payload.display_name is not None:
            source.display_name = payload.display_name
        if payload.status is not None:
            source.status = payload.status.value
        if payload.config_json is not None:
            adapter = self._get_adapter(source.kind)
            adapter.validate_source_config(payload.config_json)
            source.config_json = payload.config_json

        await self.uow.commit()
        await self.uow.session.refresh(source)
        return self._source_model(source)

    async def list_sources(self) -> SourceListResponse:
        items = await self.source_repo.list_all()
        return SourceListResponse(items=[self._source_model(source) for source in items])

    async def start_sync(self, source_id: UUID | str, payload: SourceSyncCreateRequest) -> SyncRunModel:
        source = await self.source_repo.get_by_id(source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")
        if source.status != SourceStatus.ACTIVE.value:
            raise BadRequestError("Archive source is not active.")

        if payload.coverage_kind != SyncCoverageKind.PARTIAL_SAMPLE and payload.sample_percent is not None:
            raise BadRequestError("sample_percent is only supported for partial_sample syncs.")

        sync_run = SyncRun(
            source_id=source.id,
            trigger_kind=payload.trigger_kind.value,
            coverage_kind=payload.coverage_kind.value,
            status=SyncRunStatus.CREATED.value,
            sample_percent=payload.sample_percent,
            include_content_types=self._serialize_content_types(payload.include_content_types),
            exclude_content_types=self._serialize_content_types(payload.exclude_content_types),
        )
        await self.sync_run_repo.add(sync_run)
        await self.uow.commit()
        await self.uow.session.refresh(sync_run)
        await self.broker.publish_queue_message(ARCHIVE_SYNC_QUEUE, {"sync_run_id": str(sync_run.id)})
        return self._sync_model(sync_run)

    async def list_syncs(self, source_id: UUID | str, *, limit: int = 20) -> SyncRunListResponse:
        source = await self.source_repo.get_by_id(source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")
        sync_runs = await self.sync_run_repo.list_by_source(source_id, limit=limit)
        items: list[SyncRunModel] = []
        for sync_run in sync_runs:
            status = await self.refresh_sync_status(sync_run.id)
            refreshed = await self.sync_run_repo.get_by_id(status.sync_run_id)
            if refreshed is not None:
                items.append(
                    self._sync_model(
                        refreshed,
                        queued_items=status.queued_items,
                        processing_items=status.processing_items,
                    )
                )
        return SyncRunListResponse(items=items)

    async def get_sync_status(self, sync_run_id: UUID | str) -> SyncRunStatusResponse:
        return await self.refresh_sync_status(sync_run_id)

    async def refresh_sync_status(self, sync_run_id: UUID | str) -> SyncRunStatusResponse:
        sync_run = await self.sync_run_repo.get_by_id(sync_run_id)
        if sync_run is None:
            raise NotFoundError("Archive sync run not found.")
        source = await self.source_repo.get_by_id(sync_run.source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")

        counts = await self.indexing_job_repo.get_sync_run_status_counts(sync_run.id)
        queued_items = counts["queued_items"]
        processing_items = counts["processing_items"]
        indexed_items = counts["indexed_items"]
        failed_items = counts["failed_items"]

        sync_run.indexed_items = indexed_items
        sync_run.failed_items = failed_items
        completed_items = max(sync_run.total_items - queued_items - processing_items, 0)
        progress = 0.0
        if sync_run.total_items:
            progress = round(min(completed_items / sync_run.total_items, 1.0), 4)

        if sync_run.status not in {SyncRunStatus.FAILED.value, SyncRunStatus.CREATED.value, SyncRunStatus.SCANNING.value}:
            if queued_items == 0 and processing_items == 0:
                sync_run.status = SyncRunStatus.COMPLETED.value
                if sync_run.completed_at is None:
                    sync_run.completed_at = datetime.now(UTC)
            else:
                sync_run.status = SyncRunStatus.INDEXING.value

        await self.uow.commit()
        await self.uow.session.refresh(sync_run)

        return SyncRunStatusResponse(
            sync_run_id=sync_run.id,
            source_id=source.id,
            source_display_name=source.display_name,
            source_kind=source.kind,
            status=sync_run.status,
            coverage_kind=sync_run.coverage_kind,
            total_items=sync_run.total_items,
            new_items=sync_run.new_items,
            updated_items=sync_run.updated_items,
            unchanged_items=sync_run.unchanged_items,
            queued_items=queued_items,
            processing_items=processing_items,
            indexed_items=indexed_items,
            failed_items=failed_items,
            skipped_items=sync_run.skipped_items,
            progress=progress,
            started_at=sync_run.started_at,
            completed_at=sync_run.completed_at,
            created_at=sync_run.created_at,
            updated_at=sync_run.updated_at,
        )

    async def _sync_asset(
        self,
        *,
        source: SourceConnection,
        corpus_item: CorpusItem,
        normalized_asset: NormalizedAsset | None,
    ) -> CorpusAsset | None:
        def _metadata_matches(existing: CorpusAsset, incoming: NormalizedAsset) -> bool:
            return (
                existing.source_relative_path == incoming.source_relative_path
                and existing.original_filename == incoming.original_filename
                and existing.mime_type == incoming.mime_type
                and existing.file_size_bytes == incoming.file_size_bytes
                and existing.duration_ms == incoming.duration_ms
                and existing.width == incoming.width
                and existing.height == incoming.height
            )

        existing_asset = await self.corpus_asset_repo.get_by_corpus_item_and_role(corpus_item.id, "primary")
        if normalized_asset is None:
            if existing_asset is not None:
                await self.uow.session.delete(existing_asset)
            return None

        if existing_asset is not None and _metadata_matches(existing_asset, normalized_asset):
            existing_asset.source_relative_path = normalized_asset.source_relative_path
            existing_asset.original_filename = normalized_asset.original_filename
            existing_asset.mime_type = normalized_asset.mime_type
            existing_asset.file_size_bytes = normalized_asset.file_size_bytes
            existing_asset.duration_ms = normalized_asset.duration_ms
            existing_asset.width = normalized_asset.width
            existing_asset.height = normalized_asset.height
            return existing_asset

        if normalized_asset.sha256 is None:
            normalized_asset.sha256 = await asyncio.to_thread(sha256_file, normalized_asset.local_path)

        if existing_asset is not None and existing_asset.sha256 == normalized_asset.sha256:
            existing_asset.source_relative_path = normalized_asset.source_relative_path
            existing_asset.original_filename = normalized_asset.original_filename
            existing_asset.mime_type = normalized_asset.mime_type
            existing_asset.file_size_bytes = normalized_asset.file_size_bytes
            existing_asset.duration_ms = normalized_asset.duration_ms
            existing_asset.width = normalized_asset.width
            existing_asset.height = normalized_asset.height
            return existing_asset

        object_key = self.media_storage.build_corpus_asset_key(
            source_slug=source.slug,
            content_type=corpus_item.content_type,
            sha256=normalized_asset.sha256,
            filename=normalized_asset.original_filename or normalized_asset.local_path.name,
        )
        await asyncio.to_thread(
            self.media_storage.put_object_file,
            bucket=self.settings.STORAGE_ARCHIVE_BUCKET,
            key=object_key,
            path=normalized_asset.local_path,
            content_type=normalized_asset.mime_type,
        )

        if existing_asset is None:
            existing_asset = CorpusAsset(corpus_item_id=corpus_item.id, role=normalized_asset.role.value, storage_bucket=self.settings.STORAGE_ARCHIVE_BUCKET, object_key=object_key, source_relative_path=normalized_asset.source_relative_path, original_filename=normalized_asset.original_filename, mime_type=normalized_asset.mime_type, file_size_bytes=normalized_asset.file_size_bytes, sha256=normalized_asset.sha256, duration_ms=normalized_asset.duration_ms, width=normalized_asset.width, height=normalized_asset.height)
            await self.corpus_asset_repo.add(existing_asset)
            await self.uow.session.flush()
            return existing_asset

        existing_asset.role = normalized_asset.role.value
        existing_asset.storage_bucket = self.settings.STORAGE_ARCHIVE_BUCKET
        existing_asset.object_key = object_key
        existing_asset.source_relative_path = normalized_asset.source_relative_path
        existing_asset.original_filename = normalized_asset.original_filename
        existing_asset.mime_type = normalized_asset.mime_type
        existing_asset.file_size_bytes = normalized_asset.file_size_bytes
        existing_asset.sha256 = normalized_asset.sha256
        existing_asset.duration_ms = normalized_asset.duration_ms
        existing_asset.width = normalized_asset.width
        existing_asset.height = normalized_asset.height
        return existing_asset

    async def _ensure_projection_job(
        self,
        *,
        projection: CorpusProjection,
        sync_run: SyncRun,
    ) -> IndexingJob | None:
        active_job = await self.indexing_job_repo.get_active_for_projection(projection.id)
        if active_job is not None:
            return None

        job = IndexingJob(
            projection_id=projection.id,
            sync_run_id=sync_run.id,
            job_kind="index_projection",
            status="queued",
        )
        await self.indexing_job_repo.add(job)
        await self.uow.session.flush()
        return job

    async def _upsert_item(
        self,
        *,
        source: SourceConnection,
        sync_run: SyncRun,
        normalized_item: NormalizedSourceItem,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        existing = await self.corpus_item_repo.get_by_source_and_external_key(source.id, normalized_item.external_key)
        queue_job: IndexingJob | None = None
        result_kind = "unchanged"

        if existing is None:
            corpus_item = CorpusItem(
                source_id=source.id,
                external_key=normalized_item.external_key,
                stable_key=normalized_item.stable_key,
                content_hash=normalized_item.content_hash,
                content_type=normalized_item.content_type.value,
                occurred_at=normalized_item.occurred_at,
                author_external_id=normalized_item.author_external_id,
                author_name=normalized_item.author_name,
                container_external_id=normalized_item.container_external_id,
                container_name=normalized_item.container_name,
                text_content=normalized_item.text_content,
                caption=normalized_item.caption,
                reply_to_external_key=normalized_item.reply_to_external_key,
                has_media=normalized_item.has_media,
                present_in_latest_sync=True,
                first_seen_at=now,
                last_seen_at=now,
                last_seen_run_id=sync_run.id,
            )
            await self.corpus_item_repo.add(corpus_item)
            await self.uow.session.flush()
            await self._sync_asset(source=source, corpus_item=corpus_item, normalized_asset=normalized_item.asset)
            projection = CorpusProjection(
                corpus_item_id=corpus_item.id,
                projection_kind=normalized_item.projection_kind.value,
                content_hash=normalized_item.content_hash,
                index_status=normalized_item.projection_status.value,
                index_error=normalized_item.projection_error,
            )
            await self.corpus_projection_repo.add(projection)
            await self.uow.session.flush()
            result_kind = "new"
            if normalized_item.projection_status == ProjectionIndexStatus.QUEUED:
                queue_job = await self._ensure_projection_job(projection=projection, sync_run=sync_run)
            return {"item_id": corpus_item.id, "result_kind": result_kind, "projection_status": normalized_item.projection_status.value, "job": queue_job}

        existing.present_in_latest_sync = True
        existing.last_seen_at = now
        existing.last_seen_run_id = sync_run.id
        projection = await self.corpus_projection_repo.get_by_corpus_item_and_kind(
            existing.id,
            normalized_item.projection_kind.value,
        )

        if existing.content_hash == normalized_item.content_hash:
            needs_repair = (
                normalized_item.projection_status == ProjectionIndexStatus.QUEUED
                and (
                    projection is None
                    or projection.content_hash != normalized_item.content_hash
                    or projection.index_status != ProjectionIndexStatus.INDEXED.value
                    or not projection.qdrant_point_id
                )
            )
            if not needs_repair:
                return {"item_id": existing.id, "result_kind": result_kind, "projection_status": projection.index_status if projection else ProjectionIndexStatus.SKIPPED.value, "job": None}

        existing.content_hash = normalized_item.content_hash
        existing.content_type = normalized_item.content_type.value
        existing.occurred_at = normalized_item.occurred_at
        existing.author_external_id = normalized_item.author_external_id
        existing.author_name = normalized_item.author_name
        existing.container_external_id = normalized_item.container_external_id
        existing.container_name = normalized_item.container_name
        existing.text_content = normalized_item.text_content
        existing.caption = normalized_item.caption
        existing.reply_to_external_key = normalized_item.reply_to_external_key
        existing.has_media = normalized_item.has_media
        await self._sync_asset(source=source, corpus_item=existing, normalized_asset=normalized_item.asset)

        if projection is None:
            projection = CorpusProjection(
                corpus_item_id=existing.id,
                projection_kind=normalized_item.projection_kind.value,
                content_hash=normalized_item.content_hash,
                index_status=normalized_item.projection_status.value,
                index_error=normalized_item.projection_error,
            )
            await self.corpus_projection_repo.add(projection)
            await self.uow.session.flush()
        else:
            projection.content_hash = normalized_item.content_hash
            projection.index_status = normalized_item.projection_status.value
            projection.index_error = normalized_item.projection_error

        result_kind = "updated"
        if normalized_item.projection_status == ProjectionIndexStatus.QUEUED:
            queue_job = await self._ensure_projection_job(projection=projection, sync_run=sync_run)
        return {"item_id": existing.id, "result_kind": result_kind, "projection_status": normalized_item.projection_status.value, "job": queue_job}

    async def process_sync_run(self, sync_run_id: UUID | str) -> None:
        sync_run = await self.sync_run_repo.get_by_id(sync_run_id)
        if sync_run is None:
            return
        if sync_run.status != SyncRunStatus.CREATED.value:
            return

        source = await self.source_repo.get_by_id(sync_run.source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")

        adapter = self._get_adapter(source.kind)
        adapter.validate_source_config(source.config_json)

        sync_run.status = SyncRunStatus.SCANNING.value
        if sync_run.started_at is None:
            sync_run.started_at = datetime.now(UTC)
        sync_run.completed_at = None
        await self.uow.commit()

        upserted_item_ids: list[UUID] = []
        queued_any_index_jobs = False
        manifest_uploaded = False
        sync_run.total_items = 0
        sync_run.new_items = 0
        sync_run.updated_items = 0
        sync_run.unchanged_items = 0
        sync_run.skipped_items = 0

        async for scanned_batch in adapter.iter_sync_run_batches(source=source, sync_run=sync_run):
            if not manifest_uploaded:
                manifest_key = self.media_storage.build_source_manifest_key(
                    source.slug,
                    sync_run.id,
                    scanned_batch.manifest_path.name,
                )
                await asyncio.to_thread(
                    self.media_storage.put_object_file,
                    bucket=self.settings.STORAGE_ARCHIVE_BUCKET,
                    key=manifest_key,
                    path=scanned_batch.manifest_path,
                    content_type="application/json",
                )
                sync_run.raw_manifest_object_key = manifest_key
                manifest_uploaded = True

            batch_queue_payloads: list[tuple[int, dict[str, str]]] = []
            for normalized_item in scanned_batch.items:
                sync_run.total_items += 1
                upsert_result = await self._upsert_item(source=source, sync_run=sync_run, normalized_item=normalized_item)
                upserted_item_ids.append(upsert_result["item_id"])
                result_kind = str(upsert_result["result_kind"])
                projection_status = str(upsert_result["projection_status"])
                job = upsert_result["job"]

                if result_kind == "new":
                    sync_run.new_items += 1
                elif result_kind == "updated":
                    sync_run.updated_items += 1
                else:
                    sync_run.unchanged_items += 1

                if projection_status == ProjectionIndexStatus.SKIPPED.value:
                    sync_run.skipped_items += 1

                if job is not None:
                    priority = {
                        ArchiveContentType.TEXT: 0,
                        ArchiveContentType.PHOTO: 1,
                        ArchiveContentType.VOICE: 2,
                        ArchiveContentType.AUDIO: 3,
                        ArchiveContentType.VIDEO: 4,
                    }.get(normalized_item.content_type, 5)
                    batch_queue_payloads.append(
                        (
                            priority,
                            {
                                "job_id": str(job.id),
                                "projection_id": str(job.projection_id),
                                "sync_run_id": str(sync_run.id),
                                "content_type": normalized_item.content_type.value,
                            },
                        )
                    )

            queued_any_index_jobs = queued_any_index_jobs or bool(batch_queue_payloads)
            await self.uow.commit()
            if batch_queue_payloads:
                batch_queue_payloads.sort(key=lambda item: item[0])
                await self.broker.publish_queue_messages(
                    ARCHIVE_INDEX_QUEUE,
                    [payload for _, payload in batch_queue_payloads],
                )

        if sync_run.coverage_kind == SyncCoverageKind.FULL_SNAPSHOT.value:
            await self.corpus_item_repo.mark_not_seen_in_full_snapshot(
                source_id=source.id,
                current_run_id=sync_run.id,
            )

        sync_run.status = SyncRunStatus.INDEXING.value if queued_any_index_jobs else SyncRunStatus.COMPLETED.value
        if not queued_any_index_jobs:
            sync_run.completed_at = datetime.now(UTC)

        await self.uow.commit()

        if self.settings.ARCHIVE_AUTO_ENRICH_ON_SYNC and self.enrichment_service is not None and upserted_item_ids:
            await self.enrichment_service.create_sync_enrichment_run(
                source=source,
                sync_run=sync_run,
                item_ids=upserted_item_ids,
            )

    async def fail_stale_sync_runs(self, *, older_than_minutes: int) -> int:
        stale_runs = await self.sync_run_repo.list_stuck_by_status(
            status=SyncRunStatus.SCANNING.value,
            older_than_minutes=older_than_minutes,
        )
        for sync_run in stale_runs:
            sync_run.status = SyncRunStatus.FAILED.value
            sync_run.completed_at = datetime.now(UTC)
        await self.uow.commit()
        return len(stale_runs)

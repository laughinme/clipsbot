from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from broker import ARCHIVE_ENRICH_QUEUE, ARCHIVE_INDEX_QUEUE, BrokerPublisher
from core.config import Settings
from core.errors import NotFoundError
from database.relational_db import (
    CorpusAsset,
    CorpusEnrichment,
    CorpusEnrichmentInterface,
    CorpusItem,
    CorpusItemInterface,
    CorpusProjection,
    CorpusProjectionInterface,
    EnrichmentJob,
    EnrichmentJobInterface,
    EnrichmentRun,
    EnrichmentRunInterface,
    IndexingJob,
    IndexingJobInterface,
    SourceConnection,
    SourceConnectionInterface,
    SyncRun,
    UoW,
)
from domain.archive import (
    ArchiveContentType,
    EnrichmentKind,
    EnrichmentRunCreateRequest,
    EnrichmentRunListResponse,
    EnrichmentRunModel,
    EnrichmentRunStatus,
    EnrichmentRunStatusResponse,
    EnrichmentStatus,
    EnrichmentTriggerKind,
    ProjectionIndexStatus,
    ProjectionKind,
)
from service.media import MediaStorageService

from .providers import ArchiveEnrichmentProviders


class ArchiveEnrichmentService:
    def __init__(
        self,
        *,
        uow: UoW,
        source_repo: SourceConnectionInterface,
        corpus_item_repo: CorpusItemInterface,
        corpus_projection_repo: CorpusProjectionInterface,
        corpus_enrichment_repo: CorpusEnrichmentInterface,
        enrichment_run_repo: EnrichmentRunInterface,
        enrichment_job_repo: EnrichmentJobInterface,
        indexing_job_repo: IndexingJobInterface,
        media_storage: MediaStorageService,
        broker: BrokerPublisher,
        providers: ArchiveEnrichmentProviders,
        settings: Settings,
    ) -> None:
        self.uow = uow
        self.source_repo = source_repo
        self.corpus_item_repo = corpus_item_repo
        self.corpus_projection_repo = corpus_projection_repo
        self.corpus_enrichment_repo = corpus_enrichment_repo
        self.enrichment_run_repo = enrichment_run_repo
        self.enrichment_job_repo = enrichment_job_repo
        self.indexing_job_repo = indexing_job_repo
        self.media_storage = media_storage
        self.broker = broker
        self.providers = providers
        self.settings = settings

    def _serialize_uuid_list(self, values: list[UUID]) -> str | None:
        normalized = sorted({str(value) for value in values})
        return ",".join(normalized) if normalized else None

    def _deserialize_uuid_list(self, value: str | None) -> list[UUID]:
        return [UUID(part.strip()) for part in (value or "").split(",") if part.strip()]

    def _serialize_content_types(self, values: list[ArchiveContentType]) -> str | None:
        normalized = sorted({value.value for value in values})
        return ",".join(normalized) if normalized else None

    def _deserialize_content_types(self, value: str | None) -> list[ArchiveContentType]:
        return [ArchiveContentType(part.strip()) for part in (value or "").split(",") if part.strip()]

    def _primary_asset(self, item: CorpusItem) -> CorpusAsset | None:
        return next((asset for asset in item.assets if asset.role == "primary"), None)

    def _enrichment(self, item: CorpusItem, kind: EnrichmentKind) -> CorpusEnrichment | None:
        return next((entry for entry in item.enrichments if entry.enrichment_kind == kind.value), None)

    def _derived_projection(self, item: CorpusItem) -> CorpusProjection | None:
        return next(
            (projection for projection in item.projections if projection.projection_kind == ProjectionKind.DERIVED_TEXT.value),
            None,
        )

    def _summary_source_hash(self, item: CorpusItem) -> str:
        ocr = self._enrichment(item, EnrichmentKind.OCR_RAW)
        transcript = self._enrichment(item, EnrichmentKind.TRANSCRIPT_RAW)
        payload = {
            "item_hash": item.content_hash,
            "ocr": ocr.text if ocr and ocr.status == EnrichmentStatus.COMPLETED.value else None,
            "transcript": transcript.text if transcript and transcript.status == EnrichmentStatus.COMPLETED.value else None,
        }
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    def _enrichment_source_hash(self, item: CorpusItem, kind: EnrichmentKind, asset: CorpusAsset | None) -> str:
        payload = {
            "item_hash": item.content_hash,
            "kind": kind.value,
            "asset_sha256": asset.sha256 if asset else None,
            "asset_mime_type": asset.mime_type if asset else None,
        }
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    def _derived_text_hash(self, item: CorpusItem) -> str:
        ocr = self._enrichment(item, EnrichmentKind.OCR_RAW)
        transcript = self._enrichment(item, EnrichmentKind.TRANSCRIPT_RAW)
        summary = self._enrichment(item, EnrichmentKind.SUMMARY_TEXT)
        payload = {
            "item_hash": item.content_hash,
            "ocr": ocr.text if ocr and ocr.status == EnrichmentStatus.COMPLETED.value else None,
            "transcript": transcript.text if transcript and transcript.status == EnrichmentStatus.COMPLETED.value else None,
            "summary": summary.text if summary and summary.status == EnrichmentStatus.COMPLETED.value else None,
        }
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()

    def build_derived_text(self, item: CorpusItem) -> str:
        source_name = item.source.display_name if item.source is not None else "Unknown Source"
        container = item.container_name or item.container_external_id or "Unknown container"
        author = item.author_name or item.author_external_id or "Unknown author"
        ocr = self._enrichment(item, EnrichmentKind.OCR_RAW)
        transcript = self._enrichment(item, EnrichmentKind.TRANSCRIPT_RAW)
        summary = self._enrichment(item, EnrichmentKind.SUMMARY_TEXT)
        parts = [
            f"type: {item.content_type}",
            f"source: {source_name} / {container}",
            f"author: {author}",
            f"message_text: {item.text_content or ''}",
            f"caption: {item.caption or ''}",
            f"ocr_text: {ocr.text if ocr and ocr.status == EnrichmentStatus.COMPLETED.value else ''}",
            f"transcript: {transcript.text if transcript and transcript.status == EnrichmentStatus.COMPLETED.value else ''}",
            f"summary: {summary.text if summary and summary.status == EnrichmentStatus.COMPLETED.value else ''}",
        ]
        normalized = "\n".join(part for part in parts if part.split(":", 1)[-1].strip())
        return normalized.strip()

    def _supports_ocr(self, item: CorpusItem, asset: CorpusAsset | None) -> bool:
        return item.content_type == ArchiveContentType.PHOTO.value and asset is not None

    def _supports_transcript(self, item: CorpusItem, asset: CorpusAsset | None) -> bool:
        return item.content_type in {
            ArchiveContentType.VOICE.value,
            ArchiveContentType.AUDIO.value,
            ArchiveContentType.VIDEO.value,
        } and asset is not None

    def _supports_summary(self, item: CorpusItem) -> bool:
        return item.content_type in {
            ArchiveContentType.PHOTO.value,
            ArchiveContentType.VOICE.value,
            ArchiveContentType.AUDIO.value,
            ArchiveContentType.VIDEO.value,
        }

    def _applicable_kinds(self, item: CorpusItem) -> list[EnrichmentKind]:
        asset = self._primary_asset(item)
        kinds: list[EnrichmentKind] = []
        if self._supports_ocr(item, asset):
            kinds.append(EnrichmentKind.OCR_RAW)
        if self._supports_transcript(item, asset):
            kinds.append(EnrichmentKind.TRANSCRIPT_RAW)
        if self._supports_summary(item):
            kinds.append(EnrichmentKind.SUMMARY_TEXT)
        return kinds

    def _provider_details(
        self,
        *,
        kind: EnrichmentKind,
        asset: CorpusAsset | None,
    ) -> tuple[str, str | None]:
        if kind == EnrichmentKind.OCR_RAW:
            return (
                "vision" if self.settings.OCR_PROVIDER == "vision" else "stub",
                "DOCUMENT_TEXT_DETECTION" if self.settings.OCR_PROVIDER == "vision" else None,
            )
        if kind == EnrichmentKind.TRANSCRIPT_RAW:
            if self.settings.TRANSCRIPT_PROVIDER != "speech_v2":
                return ("stub", None)
            duration_seconds = ((asset.duration_ms if asset is not None else 0) or 0) / 1000
            model = self.settings.STT_SHORT_MODEL if duration_seconds and duration_seconds <= 60 else self.settings.STT_LONG_MODEL
            return ("speech_v2", model)
        return (
            "vertex" if self.settings.SUMMARY_PROVIDER == "vertex" else "stub",
            self.settings.GEMINI_SUMMARY_MODEL if self.settings.SUMMARY_PROVIDER == "vertex" else None,
        )

    async def _ensure_enrichment_row(
        self,
        *,
        item: CorpusItem,
        kind: EnrichmentKind,
        asset: CorpusAsset | None,
    ) -> CorpusEnrichment:
        expected_hash = self._summary_source_hash(item) if kind == EnrichmentKind.SUMMARY_TEXT else self._enrichment_source_hash(item, kind, asset)
        existing = self._enrichment(item, kind)
        if existing is not None:
            if existing.source_content_hash != expected_hash:
                existing.source_content_hash = expected_hash
                existing.status = EnrichmentStatus.QUEUED.value
                existing.error = None
                existing.source_asset_id = asset.id if asset else None
            return existing

        row = CorpusEnrichment(
            corpus_item_id=item.id,
            source_asset_id=asset.id if asset else None,
            enrichment_kind=kind.value,
            source_content_hash=expected_hash,
            provider="stub",
            provider_model=None,
            status=EnrichmentStatus.QUEUED.value,
        )
        await self.corpus_enrichment_repo.add(row)
        await self.uow.session.flush()
        item.enrichments.append(row)
        return row

    async def _ensure_enrichment_job(
        self,
        *,
        enrichment_run: EnrichmentRun,
        item: CorpusItem,
        kind: EnrichmentKind,
    ) -> tuple[EnrichmentJob, bool]:
        existing = await self.enrichment_job_repo.get_for_run_item_kind(
            enrichment_run.id,
            item.id,
            kind.value,
        )
        if existing is not None:
            if existing.status != EnrichmentStatus.COMPLETED.value:
                existing.status = EnrichmentStatus.QUEUED.value
                existing.started_at = None
                existing.completed_at = None
                existing.last_error = None
            return existing, False

        job = EnrichmentJob(
            enrichment_run_id=enrichment_run.id,
            corpus_item_id=item.id,
            enrichment_kind=kind.value,
            status=EnrichmentStatus.QUEUED.value,
        )
        try:
            async with self.uow.session.begin_nested():
                await self.enrichment_job_repo.add(job)
                await self.uow.session.flush()
            return job, True
        except IntegrityError:
            existing = await self.enrichment_job_repo.get_for_run_item_kind(
                enrichment_run.id,
                item.id,
                kind.value,
            )
            if existing is None:
                raise
            if existing.status != EnrichmentStatus.COMPLETED.value:
                existing.status = EnrichmentStatus.QUEUED.value
                existing.started_at = None
                existing.completed_at = None
                existing.last_error = None
            return existing, False

    async def _ensure_projection_index_job(
        self,
        *,
        projection: CorpusProjection,
        sync_run_id: UUID | None,
    ) -> IndexingJob | None:
        sync_run_id = sync_run_id or projection.corpus_item.last_seen_run_id
        if sync_run_id is None:
            raise RuntimeError("Derived projection requires a sync run reference for indexing.")

        active_job = await self.indexing_job_repo.get_active_for_projection(projection.id)
        if active_job is not None:
            return None

        job = IndexingJob(
            projection_id=projection.id,
            sync_run_id=sync_run_id,
            job_kind="index_projection",
            status="queued",
        )
        await self.indexing_job_repo.add(job)
        await self.uow.session.flush()
        return job

    async def _upsert_derived_projection(
        self,
        *,
        item: CorpusItem,
        sync_run_id: UUID | None,
    ) -> list[dict[str, str]]:
        derived_text = self.build_derived_text(item)
        if not derived_text:
            return []
        resolved_sync_run_id = sync_run_id or item.last_seen_run_id

        projection = self._derived_projection(item)
        content_hash = self._derived_text_hash(item)
        if projection is None:
            projection = CorpusProjection(
                corpus_item_id=item.id,
                projection_kind=ProjectionKind.DERIVED_TEXT.value,
                content_hash=content_hash,
                index_status=ProjectionIndexStatus.QUEUED.value,
                index_error=None,
            )
            try:
                async with self.uow.session.begin_nested():
                    await self.corpus_projection_repo.add(projection)
                    await self.uow.session.flush()
                item.projections.append(projection)
            except IntegrityError:
                projection = await self.corpus_projection_repo.get_by_corpus_item_and_kind(
                    item.id,
                    ProjectionKind.DERIVED_TEXT.value,
                )
                if projection is None:
                    raise
                projection.content_hash = content_hash
                projection.index_status = ProjectionIndexStatus.QUEUED.value
                projection.index_error = None
        else:
            if projection.content_hash == content_hash and projection.index_status == ProjectionIndexStatus.INDEXED.value:
                return []
            projection.content_hash = content_hash
            projection.index_status = ProjectionIndexStatus.QUEUED.value
            projection.index_error = None

        job = await self._ensure_projection_index_job(projection=projection, sync_run_id=resolved_sync_run_id)
        if job is None:
            return []
        return [
            {
                "job_id": str(job.id),
                "projection_id": str(job.projection_id),
                "sync_run_id": str(job.sync_run_id),
            }
        ]

    def _run_model(self, run: EnrichmentRun) -> EnrichmentRunModel:
        return EnrichmentRunModel(
            id=run.id,
            source_id=run.source_id,
            sync_run_id=run.sync_run_id,
            trigger_kind=run.trigger_kind,
            status=run.status,
            source_ids=self._deserialize_uuid_list(run.source_ids),
            content_types=self._deserialize_content_types(run.content_types),
            present_in_latest_sync=run.present_in_latest_sync,
            sample_percent=run.sample_percent,
            total_items=run.total_items,
            queued_items=run.queued_items,
            processing_items=run.processing_items,
            completed_items=run.completed_items,
            failed_items=run.failed_items,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def refresh_enrichment_run_status(self, enrichment_run_id: UUID | str) -> EnrichmentRunStatusResponse:
        run = await self.enrichment_run_repo.get_by_id(enrichment_run_id)
        if run is None:
            raise NotFoundError("Archive enrichment run not found.")

        counts = await self.enrichment_job_repo.get_run_status_counts(run.id)
        observed_total = (
            counts["queued_items"]
            + counts["processing_items"]
            + counts["completed_items"]
            + counts["failed_items"]
        )
        run.total_items = max(run.total_items, observed_total)
        run.queued_items = counts["queued_items"]
        run.processing_items = counts["processing_items"]
        run.completed_items = counts["completed_items"]
        run.failed_items = counts["failed_items"]

        if run.queued_items == 0 and run.processing_items == 0:
            run.status = (
                EnrichmentRunStatus.FAILED.value
                if run.failed_items > 0
                else EnrichmentRunStatus.COMPLETED.value
            )
            if run.completed_at is None:
                run.completed_at = datetime.now(UTC)
        else:
            run.status = EnrichmentRunStatus.RUNNING.value

        await self.uow.commit()
        await self.uow.session.refresh(run)

        processed = run.completed_items + run.failed_items
        progress = round(min(processed / run.total_items, 1.0), 4) if run.total_items else 0.0
        return EnrichmentRunStatusResponse(
            enrichment_run_id=run.id,
            status=run.status,
            source_ids=self._deserialize_uuid_list(run.source_ids),
            content_types=self._deserialize_content_types(run.content_types),
            present_in_latest_sync=run.present_in_latest_sync,
            sample_percent=run.sample_percent,
            total_items=run.total_items,
            queued_items=run.queued_items,
            processing_items=run.processing_items,
            completed_items=run.completed_items,
            failed_items=run.failed_items,
            progress=progress,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    async def list_enrichment_runs(self, source_id: UUID | str, *, limit: int = 20) -> EnrichmentRunListResponse:
        source = await self.source_repo.get_by_id(source_id)
        if source is None:
            raise NotFoundError("Archive source not found.")
        runs = await self.enrichment_run_repo.list_by_source(source_id, limit=limit)
        return EnrichmentRunListResponse(items=[self._run_model(run) for run in runs])

    async def get_enrichment_run(self, enrichment_run_id: UUID | str) -> EnrichmentRunStatusResponse:
        return await self.refresh_enrichment_run_status(enrichment_run_id)

    def _select_sample(self, *, stable_key: str, sample_percent: int | None) -> bool:
        if not sample_percent or sample_percent >= 100:
            return True
        bucket = int(hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < sample_percent

    async def _create_run_and_jobs(
        self,
        *,
        source_ids: list[UUID],
        items: list[CorpusItem],
        trigger_kind: EnrichmentTriggerKind,
        sync_run_id: UUID | None,
        sample_percent: int | None,
        present_in_latest_sync: bool | None,
        content_types: list[ArchiveContentType],
    ) -> EnrichmentRunModel | None:
        filtered_items = [item for item in items if self._select_sample(stable_key=item.stable_key, sample_percent=sample_percent)]
        if not filtered_items:
            return None

        source_id = source_ids[0] if len(source_ids) == 1 else None
        run = EnrichmentRun(
            source_id=source_id,
            sync_run_id=sync_run_id,
            trigger_kind=trigger_kind.value,
            status=EnrichmentRunStatus.RUNNING.value,
            source_ids=self._serialize_uuid_list(source_ids),
            content_types=self._serialize_content_types(content_types),
            present_in_latest_sync=present_in_latest_sync,
            sample_percent=sample_percent,
            started_at=datetime.now(UTC),
        )
        await self.enrichment_run_repo.add(run)
        await self.uow.session.flush()

        queue_payloads: list[dict[str, str]] = []
        queued_jobs = 0
        for item in filtered_items:
            asset = self._primary_asset(item)
            applicable = self._applicable_kinds(item)
            if not applicable:
                continue
            for kind in applicable:
                enrichment = await self._ensure_enrichment_row(item=item, kind=kind, asset=asset)
                expected_hash = self._summary_source_hash(item) if kind == EnrichmentKind.SUMMARY_TEXT else self._enrichment_source_hash(item, kind, asset)
                is_fresh = (
                    enrichment.status == EnrichmentStatus.COMPLETED.value
                    and enrichment.source_content_hash == expected_hash
                )
                if is_fresh:
                    continue
                job, _ = await self._ensure_enrichment_job(enrichment_run=run, item=item, kind=kind)
                queue_payloads.append(
                    {
                        "job_id": str(job.id),
                        "enrichment_run_id": str(run.id),
                        "corpus_item_id": str(item.id),
                        "enrichment_kind": kind.value,
                    }
                )
                queued_jobs += 1

        run.total_items = queued_jobs
        run.queued_items = queued_jobs
        if queued_jobs == 0:
            run.status = EnrichmentRunStatus.COMPLETED.value
            run.completed_at = datetime.now(UTC)

        await self.uow.commit()
        if queue_payloads:
            await self.broker.publish_queue_messages(ARCHIVE_ENRICH_QUEUE, queue_payloads)
        await self.uow.session.refresh(run)
        return self._run_model(run)

    async def start_manual_enrichment_run(self, payload: EnrichmentRunCreateRequest) -> EnrichmentRunModel | None:
        source_ids = list(payload.source_ids)
        content_types = payload.content_types or [
            ArchiveContentType.TEXT,
            ArchiveContentType.PHOTO,
            ArchiveContentType.VOICE,
            ArchiveContentType.AUDIO,
            ArchiveContentType.VIDEO,
        ]
        items = await self.corpus_item_repo.list_for_enrichment_scope(
            source_ids=source_ids or None,
            content_types=[content_type.value for content_type in content_types],
            present_in_latest_sync=payload.present_in_latest_sync,
        )
        return await self._create_run_and_jobs(
            source_ids=source_ids,
            items=items,
            trigger_kind=EnrichmentTriggerKind.MANUAL,
            sync_run_id=None,
            sample_percent=payload.sample_percent,
            present_in_latest_sync=payload.present_in_latest_sync,
            content_types=content_types,
        )

    async def create_sync_enrichment_run(
        self,
        *,
        source: SourceConnection,
        sync_run: SyncRun,
        item_ids: list[UUID],
    ) -> EnrichmentRunModel | None:
        items = await self.corpus_item_repo.list_by_ids(item_ids)
        content_types = [
            ArchiveContentType.TEXT,
            ArchiveContentType.PHOTO,
            ArchiveContentType.VOICE,
            ArchiveContentType.AUDIO,
            ArchiveContentType.VIDEO,
        ]
        return await self._create_run_and_jobs(
            source_ids=[source.id],
            items=items,
            trigger_kind=EnrichmentTriggerKind.SYNC,
            sync_run_id=sync_run.id,
            sample_percent=sync_run.sample_percent,
            present_in_latest_sync=None,
            content_types=content_types,
        )

    async def _run_ocr(self, *, item: CorpusItem, asset: CorpusAsset, enrichment: CorpusEnrichment, payload: bytes) -> None:
        result = await self.providers.ocr.extract(item=item, asset=asset, payload=payload)
        enrichment.text = result.text
        enrichment.language_code = result.language_code
        enrichment.provider = result.provider
        enrichment.provider_model = result.provider_model
        enrichment.status = EnrichmentStatus.COMPLETED.value
        enrichment.error = None

    async def _run_transcript(self, *, item: CorpusItem, asset: CorpusAsset, enrichment: CorpusEnrichment, payload: bytes) -> None:
        result = await self.providers.transcript.transcribe(item=item, asset=asset, payload=payload)
        enrichment.text = result.text
        enrichment.language_code = result.language_code
        enrichment.provider = result.provider
        enrichment.provider_model = result.provider_model
        enrichment.status = EnrichmentStatus.COMPLETED.value
        enrichment.error = None

    async def _run_summary(self, *, item: CorpusItem, enrichment: CorpusEnrichment) -> None:
        ocr = self._enrichment(item, EnrichmentKind.OCR_RAW)
        transcript = self._enrichment(item, EnrichmentKind.TRANSCRIPT_RAW)
        result = await self.providers.summary.summarize(
            item=item,
            ocr_text=ocr.text if ocr and ocr.status == EnrichmentStatus.COMPLETED.value else None,
            transcript_text=transcript.text if transcript and transcript.status == EnrichmentStatus.COMPLETED.value else None,
        )
        enrichment.text = result.text
        enrichment.language_code = result.language_code
        enrichment.provider = result.provider
        enrichment.provider_model = result.provider_model
        enrichment.status = EnrichmentStatus.COMPLETED.value
        enrichment.error = None

    async def process_enrichment_job(self, job_id: UUID | str) -> None:
        job = await self.enrichment_job_repo.get_by_id(job_id)
        if job is None:
            return
        if job.status == EnrichmentStatus.COMPLETED.value:
            return
        if job.corpus_item is None or job.enrichment_run is None:
            raise NotFoundError("Archive enrichment job is missing its corpus item or run.")

        item = job.corpus_item
        asset = self._primary_asset(item)
        kind = EnrichmentKind(job.enrichment_kind)
        enrichment = await self._ensure_enrichment_row(item=item, kind=kind, asset=asset)

        job.status = EnrichmentStatus.PROCESSING.value
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        enrichment.status = EnrichmentStatus.PROCESSING.value
        enrichment.error = None
        await self.uow.commit()

        try:
            payload = None
            followup_enrichment_payloads: list[dict[str, str]] = []
            if kind in {EnrichmentKind.OCR_RAW, EnrichmentKind.TRANSCRIPT_RAW}:
                if asset is None:
                    raise RuntimeError("Enrichment requires a primary asset.")
                payload = await asyncio.to_thread(
                    self.media_storage.get_object_bytes,
                    bucket=asset.storage_bucket,
                    key=asset.object_key,
                )

            if kind == EnrichmentKind.OCR_RAW:
                assert asset is not None and payload is not None
                await self._run_ocr(item=item, asset=asset, enrichment=enrichment, payload=payload)
                summary_job, created_summary_job = await self._ensure_enrichment_job(
                    enrichment_run=job.enrichment_run,
                    item=item,
                    kind=EnrichmentKind.SUMMARY_TEXT,
                )
                if created_summary_job:
                    job.enrichment_run.total_items += 1
                    job.enrichment_run.queued_items += 1
                followup_enrichment_payloads.append(
                    {
                        "job_id": str(summary_job.id),
                        "enrichment_run_id": str(summary_job.enrichment_run_id),
                        "corpus_item_id": str(summary_job.corpus_item_id),
                        "enrichment_kind": summary_job.enrichment_kind,
                    }
                )
            elif kind == EnrichmentKind.TRANSCRIPT_RAW:
                assert asset is not None and payload is not None
                await self._run_transcript(item=item, asset=asset, enrichment=enrichment, payload=payload)
                summary_job, created_summary_job = await self._ensure_enrichment_job(
                    enrichment_run=job.enrichment_run,
                    item=item,
                    kind=EnrichmentKind.SUMMARY_TEXT,
                )
                if created_summary_job:
                    job.enrichment_run.total_items += 1
                    job.enrichment_run.queued_items += 1
                followup_enrichment_payloads.append(
                    {
                        "job_id": str(summary_job.id),
                        "enrichment_run_id": str(summary_job.enrichment_run_id),
                        "corpus_item_id": str(summary_job.corpus_item_id),
                        "enrichment_kind": summary_job.enrichment_kind,
                    }
                )
            else:
                await self._run_summary(item=item, enrichment=enrichment)

            projection_payloads = await self._upsert_derived_projection(
                item=item,
                sync_run_id=job.enrichment_run.sync_run_id,
            )
            job.status = EnrichmentStatus.COMPLETED.value
            job.completed_at = datetime.now(UTC)
            job.last_error = None
            await self.uow.commit()

            if followup_enrichment_payloads:
                await self.broker.publish_queue_messages(ARCHIVE_ENRICH_QUEUE, followup_enrichment_payloads)
            if projection_payloads:
                await self.broker.publish_queue_messages(ARCHIVE_INDEX_QUEUE, projection_payloads)
        except Exception as exc:
            await self.uow.session.rollback()
            failed = await self.enrichment_job_repo.get_by_id(job_id)
            if failed is None or failed.corpus_item is None:
                raise
            failed_enrichment = await self.corpus_enrichment_repo.get_by_item_and_kind(
                failed.corpus_item_id,
                failed.enrichment_kind,
            )
            if failed_enrichment is not None:
                asset = self._primary_asset(failed.corpus_item)
                provider, provider_model = self._provider_details(
                    kind=EnrichmentKind(failed.enrichment_kind),
                    asset=asset,
                )
                failed_enrichment.provider = provider
                failed_enrichment.provider_model = provider_model
                failed_enrichment.status = EnrichmentStatus.FAILED.value
                failed_enrichment.error = str(exc)
            failed.status = EnrichmentStatus.FAILED.value
            failed.last_error = str(exc)
            failed.completed_at = datetime.now(UTC)
            await self.uow.commit()
            raise

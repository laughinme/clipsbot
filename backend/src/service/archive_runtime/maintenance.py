from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from broker import ARCHIVE_ENRICH_QUEUE, ARCHIVE_INDEX_QUEUE, BrokerPublisher
from core.config import get_settings
from database.relational_db import (
    ClipsInterface,
    CorpusAssetInterface,
    CorpusEnrichmentInterface,
    CorpusItemInterface,
    CorpusProjectionInterface,
    EnrichmentJobInterface,
    EnrichmentRunInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    SyncRunInterface,
    UoW,
    get_session_factory,
)
from domain.archive import EnrichmentRunStatus, SyncRunStatus
from service.archive_corpus import ArchiveSourceService, get_source_adapter_registry
from service.archive_enrichments import ArchiveEnrichmentService, get_archive_enrichment_providers
from service.media import get_media_storage_service


def _build_archive_enrichment_service(session) -> ArchiveEnrichmentService:
    settings = get_settings()
    return ArchiveEnrichmentService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        corpus_enrichment_repo=CorpusEnrichmentInterface(session),
        enrichment_run_repo=EnrichmentRunInterface(session),
        enrichment_job_repo=EnrichmentJobInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        media_storage=get_media_storage_service(),
        broker=BrokerPublisher(settings),
        providers=get_archive_enrichment_providers(
            settings=settings,
            gcs_staging=None,
        ),
        settings=settings,
    )


def _build_archive_source_service(session) -> ArchiveSourceService:
    settings = get_settings()
    return ArchiveSourceService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        sync_run_repo=SyncRunInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_asset_repo=CorpusAssetInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        media_storage=get_media_storage_service(),
        broker=BrokerPublisher(settings),
        settings=settings,
        adapter_registry=get_source_adapter_registry(),
        enrichment_service=_build_archive_enrichment_service(session),
    )


async def cleanup_stale_uploads() -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = ClipsInterface(session)
        updated = await repo.mark_stale_uploads_failed()
        await session.commit()
        return updated


async def requeue_stale_sync_runs(*, startup: bool) -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        source_service = _build_archive_source_service(session)
        older_than_minutes = (
            settings.ARCHIVE_SYNC_STARTUP_RECOVERY_OLDER_THAN_MINUTES
            if startup
            else settings.ARCHIVE_SYNC_STALE_PROCESSING_MINUTES
        )
        return await source_service.requeue_stale_sync_runs(older_than_minutes=older_than_minutes)


async def requeue_stale_indexing_jobs(*, startup: bool) -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        job_repo = IndexingJobInterface(session)
        projection_repo = CorpusProjectionInterface(session)
        older_than_minutes = (
            settings.ARCHIVE_STARTUP_RECOVERY_OLDER_THAN_MINUTES
            if startup
            else settings.ARCHIVE_STALE_PROCESSING_MINUTES
        )

        if startup:
            recovered = await job_repo.bulk_requeue_processing(
                older_than_minutes=older_than_minutes,
                last_error="recovered_after_restart",
            )
            projection_ids = [projection_id for _, projection_id, _ in recovered]
            await projection_repo.bulk_requeue_processing(projection_ids=projection_ids)
            payloads = [
                {
                    "job_id": str(job_id),
                    "projection_id": str(projection_id),
                    "sync_run_id": str(sync_run_id),
                }
                for job_id, projection_id, sync_run_id in recovered
            ]
            await session.commit()
        else:
            stuck_jobs = await job_repo.list_stuck_processing(older_than_minutes=older_than_minutes)
            payloads: list[dict[str, str]] = []
            for job in stuck_jobs:
                if job.projection is None:
                    continue
                if job.attempts >= settings.EMBEDDING_REQUEST_MAX_RETRIES:
                    job.status = "failed"
                    job.last_error = "processing_timeout"
                    job.completed_at = datetime.now(UTC)
                    job.projection.index_status = "failed"
                    job.projection.index_error = "processing_timeout"
                    continue

                job.status = "queued"
                job.started_at = None
                job.last_error = "requeued_after_timeout"
                job.projection.index_status = "queued"
                job.projection.index_error = None
                payloads.append(
                    {
                        "job_id": str(job.id),
                        "projection_id": str(job.projection_id),
                        "sync_run_id": str(job.sync_run_id),
                    }
                )
            await session.commit()

    if payloads:
        await BrokerPublisher(settings).publish_queue_messages(ARCHIVE_INDEX_QUEUE, payloads)
    return len(payloads)


async def requeue_stale_enrichment_jobs(*, startup: bool) -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        job_repo = EnrichmentJobInterface(session)
        enrichment_repo = CorpusEnrichmentInterface(session)
        older_than_minutes = (
            settings.ARCHIVE_STARTUP_RECOVERY_OLDER_THAN_MINUTES
            if startup
            else settings.ARCHIVE_ENRICHMENT_STALE_PROCESSING_MINUTES
        )

        if startup:
            recovered = await job_repo.bulk_requeue_processing(
                older_than_minutes=older_than_minutes,
                last_error="recovered_after_restart",
            )
            payloads = [
                {
                    "job_id": str(job_id),
                    "corpus_item_id": str(corpus_item_id),
                    "enrichment_kind": enrichment_kind,
                    "enrichment_run_id": str(enrichment_run_id),
                }
                for job_id, corpus_item_id, enrichment_kind, enrichment_run_id in recovered
            ]
            await session.commit()
        else:
            stuck_jobs = await job_repo.list_stuck_processing(older_than_minutes=older_than_minutes)
            payloads: list[dict[str, str]] = []
            for job in stuck_jobs:
                enrichment = await enrichment_repo.get_by_item_and_kind(job.corpus_item_id, job.enrichment_kind)
                if job.attempts >= settings.EMBEDDING_REQUEST_MAX_RETRIES:
                    job.status = "failed"
                    job.last_error = "processing_timeout"
                    job.completed_at = datetime.now(UTC)
                    if enrichment is not None:
                        enrichment.status = "failed"
                        enrichment.error = "processing_timeout"
                    continue

                job.status = "queued"
                job.started_at = None
                job.last_error = "requeued_after_timeout"
                if enrichment is not None:
                    enrichment.status = "queued"
                    enrichment.error = None
                payloads.append(
                    {
                        "job_id": str(job.id),
                        "corpus_item_id": str(job.corpus_item_id),
                        "enrichment_kind": job.enrichment_kind,
                        "enrichment_run_id": str(job.enrichment_run_id),
                    }
                )
            await session.commit()

    if payloads:
        await BrokerPublisher(settings).publish_queue_messages(ARCHIVE_ENRICH_QUEUE, payloads)
    return len(payloads)


async def refresh_active_sync_run_statuses() -> int:
    session_factory = get_session_factory()
    refreshed = 0
    async with session_factory() as session:
        source_service = _build_archive_source_service(session)
        active_runs = await source_service.sync_run_repo.list_by_statuses(
            [
                SyncRunStatus.SCANNING.value,
                SyncRunStatus.INDEXING.value,
            ]
        )
        for sync_run in active_runs:
            await source_service.refresh_sync_status(sync_run.id)
            refreshed += 1
    return refreshed


async def refresh_active_enrichment_run_statuses() -> int:
    session_factory = get_session_factory()
    refreshed = 0
    async with session_factory() as session:
        enrichment_service = _build_archive_enrichment_service(session)
        active_runs = await enrichment_service.enrichment_run_repo.list_by_statuses(
            [
                EnrichmentRunStatus.CREATED.value,
                EnrichmentRunStatus.RUNNING.value,
            ]
        )
        for run in active_runs:
            await enrichment_service.refresh_enrichment_run_status(run.id)
            refreshed += 1
    return refreshed

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO

from aio_pika import IncomingMessage, connect_robust
from mutagen.mp3 import MP3

from broker import (
    ARCHIVE_ENRICH_QUEUE,
    ARCHIVE_INDEX_QUEUE,
    ARCHIVE_SYNC_QUEUE,
    CLIPS_PROCESS_QUEUE,
    MAINTENANCE_QUEUE,
    BrokerPublisher,
    ensure_topology,
)
from core.config import configure_logging, get_settings
from core.errors import NotFoundError
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
    dispose_engine,
    get_session_factory,
    wait_for_db,
)
from integrations.embeddings import get_embedding_provider
from integrations.gcs_staging import get_gcs_staging_service
from integrations.qdrant import get_qdrant_service
from service.archive_corpus import ArchiveSourceService, get_source_adapter_registry
from service.archive_enrichments import ArchiveEnrichmentService, get_archive_enrichment_providers
from service.media import get_media_storage_service
from service.semantic_search import SemanticSearchService


logger = logging.getLogger(__name__)


async def _convert_audio_to_mp3(payload: bytes) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "128k",
        "-f",
        "mp3",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(payload)
    if process.returncode != 0:
        error_text = stderr.decode("utf-8", errors="replace").strip() or "ffmpeg conversion failed"
        raise RuntimeError(error_text)
    return stdout


async def _process_clip_uploaded(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    storage = get_media_storage_service()

    async with session_factory() as session:
        repo = ClipsInterface(session)
        clip = await repo.get_by_id(payload["clip_id"])
        if clip is None or not clip.object_key:
            logger.warning("Clip %s not found during worker processing", payload["clip_id"])
            await session.commit()
            return

        try:
            content = await asyncio.to_thread(
                lambda: storage.get_object_bytes(bucket=payload["bucket"], key=payload["object_key"])
            )
            converted = False
            try:
                audio = MP3(BytesIO(content))
                final_content = content
            except Exception:
                final_content = await _convert_audio_to_mp3(content)
                audio = MP3(BytesIO(final_content))
                converted = True

            if converted:
                await asyncio.to_thread(
                    lambda: storage.put_object_bytes(
                        bucket=payload["bucket"],
                        key=payload["object_key"],
                        payload=final_content,
                        content_type="audio/mpeg",
                    )
                )

            clip.bucket = payload["bucket"]
            clip.object_key = payload["object_key"]
            clip.size_bytes = len(final_content)
            clip.duration_ms = int(audio.info.length * 1000)
            clip.mime_type = "audio/mpeg"
            clip.status = "ready"
        except Exception as exc:
            logger.exception("Failed to process clip %s: %s", payload["clip_id"], exc)
            clip.status = "failed"

        await session.commit()


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
            gcs_staging=get_gcs_staging_service(),
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


def _build_semantic_search_service(session) -> SemanticSearchService:
    settings = get_settings()
    return SemanticSearchService(
        uow=UoW(session),
        source_repo=SourceConnectionInterface(session),
        corpus_item_repo=CorpusItemInterface(session),
        corpus_projection_repo=CorpusProjectionInterface(session),
        indexing_job_repo=IndexingJobInterface(session),
        embeddings=get_embedding_provider(),
        qdrant=get_qdrant_service(),
        media_storage=get_media_storage_service(),
        settings=settings,
    )


async def _process_archive_sync(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = _build_archive_source_service(session)
        try:
            await service.process_sync_run(payload["sync_run_id"])
            try:
                await service.refresh_sync_status(payload["sync_run_id"])
            except NotFoundError:
                logger.info("Archive sync run %s was removed before refresh; skipping status update", payload["sync_run_id"])
        except Exception:
            sync_run = await service.sync_run_repo.get_by_id(payload["sync_run_id"])
            if sync_run is not None:
                sync_run.status = "failed"
                sync_run.completed_at = datetime.now(timezone.utc)
                await service.uow.commit()
            raise


async def _process_archive_enrichment(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        enrichment_service = _build_archive_enrichment_service(session)
        await enrichment_service.process_enrichment_job(payload["job_id"])
        try:
            await enrichment_service.refresh_enrichment_run_status(payload["enrichment_run_id"])
        except NotFoundError:
            logger.info(
                "Archive enrichment run %s was removed before refresh; skipping status update",
                payload["enrichment_run_id"],
            )


async def _process_archive_indexing(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        search_service = _build_semantic_search_service(session)
        source_service = _build_archive_source_service(session)
        await search_service.process_indexing_job(payload["job_id"])
        try:
            await source_service.refresh_sync_status(payload["sync_run_id"])
        except NotFoundError:
            logger.info("Archive sync run %s was removed before refresh; skipping status update", payload["sync_run_id"])


async def _requeue_indexing_jobs(*, task_name: str, session, broker: BrokerPublisher) -> None:
    settings = get_settings()
    job_repo = IndexingJobInterface(session)
    projection_repo = CorpusProjectionInterface(session)
    source_service = _build_archive_source_service(session)
    older_than_minutes = (
        settings.ARCHIVE_STARTUP_RECOVERY_OLDER_THAN_MINUTES
        if task_name == "archive.recover_interrupted_indexing_jobs"
        else settings.ARCHIVE_STALE_PROCESSING_MINUTES
    )

    if task_name == "archive.recover_interrupted_indexing_jobs":
        recovered = await job_repo.bulk_requeue_processing(
            older_than_minutes=older_than_minutes,
            last_error="recovered_after_restart",
        )
        projection_ids = [projection_id for _, projection_id, _ in recovered]
        await projection_repo.bulk_requeue_processing(projection_ids=projection_ids)
        requeue_payloads = [
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
        requeue_payloads: list[dict[str, str]] = []

        for job in stuck_jobs:
            if job.projection is None:
                continue
            if job.attempts >= settings.EMBEDDING_REQUEST_MAX_RETRIES:
                job.status = "failed"
                job.last_error = "processing_timeout"
                job.completed_at = datetime.now(timezone.utc)
                job.projection.index_status = "failed"
                job.projection.index_error = "processing_timeout"
                continue

            job.status = "queued"
            job.started_at = None
            job.last_error = "requeued_after_timeout"
            job.projection.index_status = "queued"
            job.projection.index_error = None
            requeue_payloads.append(
                {
                    "job_id": str(job.id),
                    "projection_id": str(job.projection_id),
                    "sync_run_id": str(job.sync_run_id),
                }
            )

        await session.commit()

    if requeue_payloads:
        await broker.publish_queue_messages(ARCHIVE_INDEX_QUEUE, requeue_payloads)
    for sync_run_id in {payload["sync_run_id"] for payload in requeue_payloads}:
        await source_service.refresh_sync_status(sync_run_id)
    logger.info("Processed %d archive indexing jobs for maintenance task %s", len(requeue_payloads), task_name)


async def _requeue_enrichment_jobs(*, task_name: str, session, broker: BrokerPublisher) -> None:
    settings = get_settings()
    job_repo = EnrichmentJobInterface(session)
    enrichment_repo = CorpusEnrichmentInterface(session)
    enrichment_service = _build_archive_enrichment_service(session)
    older_than_minutes = (
        settings.ARCHIVE_STARTUP_RECOVERY_OLDER_THAN_MINUTES
        if task_name == "archive.recover_interrupted_enrichment_jobs"
        else settings.ARCHIVE_ENRICHMENT_STALE_PROCESSING_MINUTES
    )

    if task_name == "archive.recover_interrupted_enrichment_jobs":
        recovered = await job_repo.bulk_requeue_processing(
            older_than_minutes=older_than_minutes,
            last_error="recovered_after_restart",
        )
        requeue_payloads = [
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
        requeue_payloads = []
        for job in stuck_jobs:
            enrichment = await enrichment_repo.get_by_item_and_kind(job.corpus_item_id, job.enrichment_kind)
            if job.attempts >= settings.EMBEDDING_REQUEST_MAX_RETRIES:
                job.status = "failed"
                job.last_error = "processing_timeout"
                job.completed_at = datetime.now(timezone.utc)
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
            requeue_payloads.append(
                {
                    "job_id": str(job.id),
                    "corpus_item_id": str(job.corpus_item_id),
                    "enrichment_kind": job.enrichment_kind,
                    "enrichment_run_id": str(job.enrichment_run_id),
                }
            )
        await session.commit()

    if requeue_payloads:
        await broker.publish_queue_messages(ARCHIVE_ENRICH_QUEUE, requeue_payloads)
    for enrichment_run_id in {payload["enrichment_run_id"] for payload in requeue_payloads}:
        try:
            await enrichment_service.refresh_enrichment_run_status(enrichment_run_id)
        except Exception:
            pass
    logger.info("Processed %d archive enrichment jobs for maintenance task %s", len(requeue_payloads), task_name)


async def _process_maintenance_job(payload: dict[str, str]) -> None:
    task_name = payload.get("task")
    session_factory = get_session_factory()
    async with session_factory() as session:
        if task_name == "clips.cleanup_stale_uploads":
            repo = ClipsInterface(session)
            updated = await repo.mark_stale_uploads_failed()
            await session.commit()
            logger.info("Marked %d stale uploads as failed", updated)
            return

        if task_name in {"archive.requeue_stale_indexing_jobs", "archive.recover_interrupted_indexing_jobs"}:
            await _requeue_indexing_jobs(task_name=task_name, session=session, broker=BrokerPublisher(get_settings()))
            return

        if task_name in {"archive.requeue_stale_enrichment_jobs", "archive.recover_interrupted_enrichment_jobs"}:
            await _requeue_enrichment_jobs(task_name=task_name, session=session, broker=BrokerPublisher(get_settings()))
            return

        if task_name == "archive.fail_stale_sync_runs":
            source_service = _build_archive_source_service(session)
            updated = await source_service.fail_stale_sync_runs(older_than_minutes=60)
            logger.info("Marked %d stale sync runs as failed", updated)
            return

        logger.info("Skipping unknown maintenance task: %s", task_name)


async def _consume_message(message: IncomingMessage, handler) -> None:
    try:
        payload = json.loads(message.body.decode("utf-8"))
        await handler(payload)
    except Exception:
        if message.redelivered:
            await message.reject(requeue=False)
        else:
            await message.nack(requeue=True)
        logger.exception("Worker handler %s failed for message %s", getattr(handler, "__name__", "unknown"), message.body.decode("utf-8", errors="replace"))
    else:
        await message.ack()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    await wait_for_db()
    await get_qdrant_service().ensure_collection()
    enabled_queues = settings.worker_queue_names

    connection = await connect_robust(
        settings.RABBITMQ_URL,
        heartbeat=settings.RABBITMQ_HEARTBEAT_SEC,
    )
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=settings.WORKER_PREFETCH_COUNT)
        await ensure_topology(channel)

        clip_queue = await channel.get_queue(CLIPS_PROCESS_QUEUE, ensure=False)
        archive_sync_queue = await channel.get_queue(ARCHIVE_SYNC_QUEUE, ensure=False)
        archive_enrich_queue = await channel.get_queue(ARCHIVE_ENRICH_QUEUE, ensure=False)
        archive_index_queue = await channel.get_queue(ARCHIVE_INDEX_QUEUE, ensure=False)
        maintenance_queue = await channel.get_queue(MAINTENANCE_QUEUE, ensure=False)

        def _enabled(queue_name: str) -> bool:
            return not enabled_queues or queue_name in enabled_queues

        if _enabled(CLIPS_PROCESS_QUEUE):
            await clip_queue.consume(lambda message: _consume_message(message, _process_clip_uploaded), no_ack=False)
        if _enabled(ARCHIVE_SYNC_QUEUE):
            await archive_sync_queue.consume(lambda message: _consume_message(message, _process_archive_sync), no_ack=False)
        if _enabled(ARCHIVE_ENRICH_QUEUE):
            await archive_enrich_queue.consume(lambda message: _consume_message(message, _process_archive_enrichment), no_ack=False)
        if _enabled(ARCHIVE_INDEX_QUEUE):
            await archive_index_queue.consume(lambda message: _consume_message(message, _process_archive_indexing), no_ack=False)
        if _enabled(MAINTENANCE_QUEUE):
            await maintenance_queue.consume(lambda message: _consume_message(message, _process_maintenance_job), no_ack=False)

        logger.info(
            "Worker started and consuming queues: %s",
            sorted(enabled_queues) if enabled_queues else "all",
        )
        await asyncio.Future()

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())

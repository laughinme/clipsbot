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
            logger.info("Starting archive sync run %s", payload["sync_run_id"])
            await service.process_sync_run(payload["sync_run_id"])
            try:
                await service.refresh_sync_status(payload["sync_run_id"])
            except NotFoundError:
                logger.info("Archive sync run %s was removed before refresh; skipping status update", payload["sync_run_id"])
            logger.info("Finished archive sync run %s", payload["sync_run_id"])
        except Exception:
            sync_run = await service.sync_run_repo.get_by_id(payload["sync_run_id"])
            if sync_run is not None:
                sync_run.status = "failed"
                sync_run.scan_heartbeat_at = None
                sync_run.completed_at = datetime.now(timezone.utc)
                await service.uow.commit()
            raise


async def _process_archive_enrichment(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        enrichment_service = _build_archive_enrichment_service(session)
        await enrichment_service.process_enrichment_job(payload["job_id"])


async def _process_archive_indexing(payload: dict[str, str]) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        search_service = _build_semantic_search_service(session)
        await search_service.process_indexing_job(payload["job_id"])


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

    try:
        while True:
            connection = None
            try:
                connection = await connect_robust(
                    settings.RABBITMQ_URL,
                    heartbeat=settings.RABBITMQ_HEARTBEAT_SEC,
                )
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=settings.WORKER_PREFETCH_COUNT)
                await ensure_topology(channel)

                clip_queue = await channel.get_queue(CLIPS_PROCESS_QUEUE, ensure=False)
                archive_sync_queue = await channel.get_queue(ARCHIVE_SYNC_QUEUE, ensure=False)
                archive_enrich_queue = await channel.get_queue(ARCHIVE_ENRICH_QUEUE, ensure=False)
                archive_index_queue = await channel.get_queue(ARCHIVE_INDEX_QUEUE, ensure=False)

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

                logger.info(
                    "Worker connected and consuming queues: %s",
                    sorted(enabled_queues) if enabled_queues else "all",
                )

                await connection.closed()

                logger.warning("RabbitMQ consumer supervisor finished; reconnecting worker consumers")
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker consumer loop crashed; reconnecting")
            finally:
                if connection is not None and not connection.is_closed:
                    await connection.close()
            await asyncio.sleep(settings.WORKER_RECONNECT_DELAY_SEC)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())

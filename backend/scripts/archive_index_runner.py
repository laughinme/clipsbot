from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select, text

from core.config import clear_settings_cache, get_settings
from database.relational_db import (
    CorpusAssetInterface,
    CorpusItemInterface,
    CorpusProjectionInterface,
    IndexingJobInterface,
    SourceConnectionInterface,
    SyncRunInterface,
    UoW,
    get_session_factory,
)
from database.relational_db.tables.indexing_jobs.indexing_jobs_table import IndexingJob
from integrations.embeddings import get_embedding_provider
from integrations.qdrant import get_qdrant_service
from broker import BrokerPublisher
from service.archive_corpus import ArchiveSourceService, get_source_adapter_registry
from service.media import get_media_storage_service
from service.semantic_search.search_service import SemanticSearchService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local archive indexing jobs for a sync run.")
    parser.add_argument("--sync-run-id", required=True, help="Sync run id to drain indexing jobs for.")
    parser.add_argument("--poll", type=float, default=2.0, help="Sleep when queue is empty before checking again.")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print indexing progress every N processed jobs.",
    )
    return parser.parse_args()


def _build_search_service(session) -> SemanticSearchService:
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


def _build_source_service(session) -> ArchiveSourceService:
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
        enrichment_service=None,
    )


async def _claim_next_job(sync_run_id: UUID) -> UUID | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await session.scalar(
            select(IndexingJob.id)
            .where(
                IndexingJob.sync_run_id == sync_run_id,
                IndexingJob.status == "queued",
            )
            .order_by(IndexingJob.created_at.asc())
            .limit(1)
        )


async def _print_progress(sync_run_id: UUID, tag: str) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        rows = await session.execute(
            text(
                """
                select status, count(*)
                from indexing_jobs
                where sync_run_id = :sync_run_id
                group by status
                order by status
                """
            ),
            {"sync_run_id": str(sync_run_id)},
        )
        print(tag, [tuple(row) for row in rows], flush=True)


async def _process_job(job_id: UUID) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = _build_search_service(session)
        await service.process_indexing_job(job_id)


async def _refresh_sync_status(sync_run_id: UUID) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = _build_source_service(session)
        await service.refresh_sync_status(sync_run_id)


async def main() -> None:
    args = _parse_args()
    clear_settings_cache()
    sync_run_id = UUID(args.sync_run_id)
    await _print_progress(sync_run_id, "index_runner_start")
    processed = 0

    while True:
        job_id = await _claim_next_job(sync_run_id)
        if job_id is None:
            await _print_progress(sync_run_id, "index_runner_idle")
            await asyncio.sleep(args.poll)
            job_id = await _claim_next_job(sync_run_id)
            if job_id is None:
                break

        try:
            await _process_job(job_id)
        except Exception as exc:
            print(f"job_failed {job_id} {type(exc).__name__}: {exc}", flush=True)

        processed += 1
        if processed % max(args.progress_every, 1) == 0:
            await _refresh_sync_status(sync_run_id)
            await _print_progress(sync_run_id, f"index_runner_processed={processed}")

    await _refresh_sync_status(sync_run_id)
    await _print_progress(sync_run_id, "index_runner_done")


if __name__ == "__main__":
    asyncio.run(main())

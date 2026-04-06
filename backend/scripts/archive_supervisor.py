from __future__ import annotations

import argparse
import asyncio
import gc
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

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
from service.archive_corpus import ArchiveSourceService, get_source_adapter_registry
from integrations.embeddings import get_embedding_provider
from integrations.qdrant import get_qdrant_service
from service.media import get_media_storage_service
from service.semantic_search.search_service import SemanticSearchService
from broker import BrokerPublisher


class _JobProgressTracker:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {
            "updated_at": None,
            "jobs": {},
        }

    async def set_stage(
        self,
        *,
        job_id: UUID,
        stage: str,
        detail: str | None = None,
    ) -> None:
        async with self._lock:
            jobs = self._state.setdefault("jobs", {})
            job = jobs.setdefault(str(job_id), {})
            now = datetime.now(UTC).isoformat()
            if job.get("stage") != stage:
                job["stage"] = stage
                job["stage_started_at"] = now
            job["detail"] = detail
            job["updated_at"] = now
            self._state["updated_at"] = now
            self._flush()

    async def clear_job(
        self,
        *,
        job_id: UUID,
        final_stage: str,
        detail: str | None = None,
    ) -> None:
        async with self._lock:
            jobs = self._state.setdefault("jobs", {})
            now = datetime.now(UTC).isoformat()
            jobs[str(job_id)] = {
                "stage": final_stage,
                "stage_started_at": now,
                "detail": detail,
                "updated_at": now,
            }
            self._state["updated_at"] = now
            self._flush()
            jobs.pop(str(job_id), None)
            self._state["updated_at"] = datetime.now(UTC).isoformat()
            self._flush()

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(self._state, ensure_ascii=True, indent=2))
        temp_path.replace(self._path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Supervise local archive sync and indexing end-to-end.")
    parser.add_argument("--sync-run-id", required=True, help="Sync run id to supervise.")
    parser.add_argument("--poll", type=float, default=2.0, help="Polling interval when idle.")
    parser.add_argument(
        "--stale-seconds",
        type=float,
        default=30.0,
        help="Reset a scanning run back to created when heartbeat is older than this threshold.",
    )
    parser.add_argument(
        "--refresh-every",
        type=int,
        default=25,
        help="Refresh sync status after this many processed indexing jobs.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="How many indexing jobs to process in parallel while in indexing state.",
    )
    parser.add_argument(
        "--media-concurrency",
        type=int,
        default=2,
        help="How many media indexing jobs to process in parallel once text backlog is exhausted.",
    )
    parser.add_argument(
        "--photo-concurrency",
        type=int,
        default=6,
        help="How many photo indexing jobs to process in parallel.",
    )
    parser.add_argument(
        "--audio-concurrency",
        type=int,
        default=6,
        help="How many voice/audio indexing jobs to process in parallel.",
    )
    parser.add_argument(
        "--video-concurrency",
        type=int,
        default=3,
        help="How many video/video_note indexing jobs to process in parallel.",
    )
    parser.add_argument(
        "--gc-every",
        type=int,
        default=10,
        help="Run Python garbage collection after this many indexing batches.",
    )
    parser.add_argument(
        "--text-first",
        type=int,
        choices=(0, 1),
        default=1,
        help="Process all queued text jobs before mixed media.",
    )
    parser.add_argument(
        "--prioritize-types",
        type=int,
        choices=(0, 1),
        default=1,
        help="When claiming from a mixed queue, prefer text/photo/voice/video ordering.",
    )
    parser.add_argument(
        "--balance-media",
        type=int,
        choices=(0, 1),
        default=1,
        help="Respect per-type media caps before using overflow slots.",
    )
    parser.add_argument(
        "--state-file",
        default="/tmp/archive-supervisor-state.json",
        help="Path to the JSON state file used by archive_monitor.",
    )
    return parser.parse_args()


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


async def _fetch_snapshot(sync_run_id: UUID) -> dict[str, object] | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        sync = (
            await session.execute(
                text(
                    """
                    select
                        id,
                        status,
                        coverage_kind,
                        total_items,
                        skipped_items,
                        indexed_items,
                        failed_items,
                        cursor,
                        scan_heartbeat_at,
                        updated_at
                    from sync_runs
                    where id = :sync_run_id
                    """
                ),
                {"sync_run_id": str(sync_run_id)},
            )
        ).mappings().first()
        if sync is None:
            return None
        jobs = (
            await session.execute(
                text(
                    """
                    select
                        coalesce(sum(case when status = 'queued' then 1 else 0 end), 0) as queued,
                        coalesce(sum(case when status = 'processing' then 1 else 0 end), 0) as processing,
                        coalesce(sum(case when status = 'done' then 1 else 0 end), 0) as done,
                        coalesce(sum(case when status = 'failed' then 1 else 0 end), 0) as failed
                    from indexing_jobs
                    where sync_run_id = :sync_run_id
                    """
                ),
                {"sync_run_id": str(sync_run_id)},
            )
        ).mappings().one()
        return {"sync": dict(sync), "jobs": dict(jobs)}


async def _reset_stale_scan_to_created(sync_run_id: UUID) -> bool:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            text(
                """
                update sync_runs
                set status = 'created',
                    scan_heartbeat_at = null,
                    completed_at = null
                where id = :sync_run_id
                  and status = 'scanning'
                """
            ),
            {"sync_run_id": str(sync_run_id)},
        )
        await session.commit()
        return bool(result.rowcount)


async def _run_scan(sync_run_id: UUID) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = _build_source_service(session)
        await service.process_sync_run(sync_run_id)
        await service.refresh_sync_status(sync_run_id)


async def _claim_jobs(
    sync_run_id: UUID,
    *,
    limit: int,
    prioritize_types: bool,
    content_types: list[str] | None = None,
) -> list[tuple[UUID, str | None]]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        jobs = await IndexingJobInterface(session).claim_for_sync_run(
            sync_run_id,
            limit=limit,
            prioritize_types=prioritize_types,
            content_types=content_types,
        )
        await session.commit()
        claimed: list[tuple[UUID, str | None]] = []
        for job in jobs:
            content_type = None
            if job.projection is not None and job.projection.corpus_item is not None:
                content_type = job.projection.corpus_item.content_type
            claimed.append((job.id, content_type))
        return claimed


async def _requeue_stale_processing_jobs(
    sync_run_id: UUID,
    *,
    active_job_ids: set[UUID],
    older_than_seconds: int = 45,
) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = IndexingJobInterface(session)
        threshold = datetime.now(UTC)
        candidates = await repo.list_processing_for_sync_run(sync_run_id)
        stale_ids = [
            job_id
            for job_id, started_at in candidates
            if job_id not in active_job_ids
            and started_at is not None
            and (threshold - started_at).total_seconds() >= older_than_seconds
        ]
        count = await repo.bulk_requeue_job_ids(
            stale_ids,
            last_error="Local archive supervisor requeued detached processing job.",
        )
        if not count:
            return 0
        await session.commit()
        return count


async def _next_queued_content_type(sync_run_id: UUID) -> str | None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await IndexingJobInterface(session).get_next_queued_content_type(sync_run_id)


async def _process_one_job(job_id: UUID, tracker: _JobProgressTracker) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = SemanticSearchService(
            uow=UoW(session),
            source_repo=SourceConnectionInterface(session),
            corpus_item_repo=CorpusItemInterface(session),
            corpus_projection_repo=CorpusProjectionInterface(session),
            indexing_job_repo=IndexingJobInterface(session),
            embeddings=get_embedding_provider(),
            qdrant=get_qdrant_service(),
            media_storage=get_media_storage_service(),
            settings=get_settings(),
        )
        async def _progress(stage: str, detail: str | None = None) -> None:
            await tracker.set_stage(job_id=job_id, stage=stage, detail=detail)

        await _progress("claimed")
        try:
            await _progress("load_job")
            await service.process_indexing_job(job_id, progress_callback=_progress)
        except Exception as exc:
            await tracker.clear_job(job_id=job_id, final_stage="failed", detail=f"{type(exc).__name__}: {exc}")
            raise
        await tracker.clear_job(job_id=job_id, final_stage="done")


async def _refresh_sync(sync_run_id: UUID) -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = _build_source_service(session)
        await service.refresh_sync_status(sync_run_id)


def _heartbeat_age(sync: dict[str, object]) -> float | None:
    heartbeat = sync.get("scan_heartbeat_at")
    if isinstance(heartbeat, datetime):
        return (datetime.now(UTC) - heartbeat).total_seconds()
    return None


def _target_concurrency(args: argparse.Namespace, next_content_type: str | None) -> int:
    return max(args.concurrency, 1)


async def _drain_completed(
    active_tasks: dict[asyncio.Task[None], tuple[UUID, str | None]],
) -> tuple[list[tuple[UUID, Exception]], int]:
    failures: list[tuple[UUID, Exception]] = []
    completed = 0
    finished = [task for task in active_tasks if task.done()]
    for task in finished:
        job_id, _content_type = active_tasks.pop(task)
        completed += 1
        try:
            await task
        except Exception as exc:
            failures.append((job_id, exc))
    return failures, completed


def _active_count(
    active_tasks: dict[asyncio.Task[None], tuple[UUID, str | None]],
    content_types: set[str],
) -> int:
    return sum(1 for _job_id, content_type in active_tasks.values() if content_type in content_types)


async def _claim_and_spawn(
    *,
    sync_run_id: UUID,
    tracker: _JobProgressTracker,
    active_tasks: dict[asyncio.Task[None], tuple[UUID, str | None]],
    limit: int,
    prioritize_types: bool,
    content_types: list[str] | None = None,
) -> int:
    claimed = await _claim_jobs(
        sync_run_id,
        limit=limit,
        prioritize_types=prioritize_types,
        content_types=content_types,
    )
    for job_id, content_type in claimed:
        active_tasks[asyncio.create_task(_process_one_job(job_id, tracker))] = (job_id, content_type)
    return len(claimed)


async def main() -> None:
    args = _parse_args()
    clear_settings_cache()
    sync_run_id = UUID(args.sync_run_id)
    tracker = _JobProgressTracker(Path(args.state_file))
    processed_jobs = 0
    processed_batches = 0
    active_tasks: dict[asyncio.Task[None], tuple[UUID, str | None]] = {}
    last_stale_requeue_at: datetime | None = None

    while True:
        snapshot = await _fetch_snapshot(sync_run_id)
        if snapshot is None:
            raise RuntimeError(f"Sync run {sync_run_id} not found")

        sync = snapshot["sync"]
        jobs = snapshot["jobs"]
        assert isinstance(sync, dict)
        assert isinstance(jobs, dict)

        status = str(sync["status"])
        queued = int(jobs["queued"])
        processing = int(jobs["processing"])
        done = int(jobs["done"])
        heartbeat_age = _heartbeat_age(sync)

        print(
            f"supervisor status={status} total={sync['total_items']} cursor={sync['cursor']} "
            f"done={done} queued={queued} processing={processing} heartbeat_age_s={heartbeat_age if heartbeat_age is not None else 'n/a'}",
            flush=True,
        )

        if status == "created":
            print("supervisor action=run_scan", flush=True)
            await _run_scan(sync_run_id)
            continue

        if status == "scanning":
            if heartbeat_age is not None and heartbeat_age > args.stale_seconds:
                reset = await _reset_stale_scan_to_created(sync_run_id)
                print(f"supervisor action=reset_stale_scan reset={reset}", flush=True)
                continue
            await asyncio.sleep(args.poll)
            continue

        if status == "indexing":
            now = datetime.now(UTC)
            if last_stale_requeue_at is None or (now - last_stale_requeue_at).total_seconds() >= 15:
                requeued = await _requeue_stale_processing_jobs(
                    sync_run_id,
                    active_job_ids={job_id for job_id, _content_type in active_tasks.values()},
                )
                if requeued:
                    print(f"supervisor action=requeue_stale_processing count={requeued}", flush=True)
                last_stale_requeue_at = now

            failures, completed_count = await _drain_completed(active_tasks)
            for job_id, result in failures:
                print(f"supervisor job_failed {job_id} {type(result).__name__}: {result}", flush=True)
            if completed_count:
                processed_jobs += completed_count
                if processed_jobs % max(args.refresh_every, 1) == 0:
                    await _refresh_sync(sync_run_id)
                if processed_batches % max(args.gc_every, 1) == 0:
                    gc.collect()

            next_content_type = await _next_queued_content_type(sync_run_id)
            target_concurrency = _target_concurrency(args, next_content_type)
            available_slots = max(target_concurrency - len(active_tasks), 0)

            claimed_total = 0
            if available_slots > 0:
                if args.text_first:
                    claimed = await _claim_and_spawn(
                        sync_run_id=sync_run_id,
                        tracker=tracker,
                        active_tasks=active_tasks,
                        limit=available_slots,
                        prioritize_types=True,
                        content_types=["text"],
                    )
                    claimed_total += claimed
                    available_slots -= claimed

                if available_slots > 0 and args.balance_media:
                    media_groups: list[tuple[list[str], int]] = [
                        (["photo"], args.photo_concurrency),
                        (["voice", "audio"], args.audio_concurrency),
                        (["video", "video_note"], args.video_concurrency),
                    ]
                    for content_types, cap in media_groups:
                        if available_slots <= 0:
                            break
                        active_group = _active_count(active_tasks, set(content_types))
                        allowed = max(min(cap, args.concurrency) - active_group, 0)
                        if allowed <= 0:
                            continue
                        claimed = await _claim_and_spawn(
                            sync_run_id=sync_run_id,
                            tracker=tracker,
                            active_tasks=active_tasks,
                            limit=min(available_slots, allowed),
                            prioritize_types=bool(args.prioritize_types),
                            content_types=content_types,
                        )
                        claimed_total += claimed
                        available_slots -= claimed

                if available_slots > 0:
                    claimed = await _claim_and_spawn(
                        sync_run_id=sync_run_id,
                        tracker=tracker,
                        active_tasks=active_tasks,
                        limit=available_slots,
                        prioritize_types=bool(args.prioritize_types),
                        content_types=None,
                    )
                    claimed_total += claimed
                    available_slots -= claimed

                if claimed_total:
                    processed_batches += 1

            if active_tasks:
                await asyncio.wait(
                    active_tasks.keys(),
                    timeout=min(args.poll, 0.5),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                continue

            if queued == 0 and processing == 0:
                await _refresh_sync(sync_run_id)
                snapshot = await _fetch_snapshot(sync_run_id)
                if snapshot is not None and str(snapshot["sync"]["status"]) == "completed":
                    print("supervisor action=completed", flush=True)
                    return
                await asyncio.sleep(args.poll)
                continue

            if available_slots == 0:
                await asyncio.sleep(min(args.poll, 0.5))
                continue

            if next_content_type is not None:
                await asyncio.sleep(min(args.poll, 0.5))
                continue

            job_ids = await _claim_jobs(
                sync_run_id,
                limit=1,
                prioritize_types=bool(args.prioritize_types),
                content_types=None,
            )
            if not job_ids:
                await _refresh_sync(sync_run_id)
                snapshot = await _fetch_snapshot(sync_run_id)
                if snapshot is not None and str(snapshot["sync"]["status"]) == "completed":
                    print("supervisor action=completed", flush=True)
                    return
                await asyncio.sleep(args.poll)
                continue
            for job_id, content_type in job_ids:
                active_tasks[asyncio.create_task(_process_one_job(job_id, tracker))] = (job_id, content_type)
            continue

        if status == "completed":
            print("supervisor action=completed", flush=True)
            return

        if status == "failed":
            raise RuntimeError(f"Sync run {sync_run_id} is failed")

        await asyncio.sleep(args.poll)


if __name__ == "__main__":
    asyncio.run(main())

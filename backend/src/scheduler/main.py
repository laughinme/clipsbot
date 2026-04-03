from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import configure_logging, get_settings
from service.archive_runtime import (
    cleanup_stale_uploads,
    refresh_active_enrichment_run_statuses,
    refresh_active_sync_run_statuses,
    requeue_stale_enrichment_jobs,
    requeue_stale_indexing_jobs,
    requeue_stale_sync_runs,
)


logger = logging.getLogger(__name__)


async def publish_cleanup_job() -> None:
    updated = await cleanup_stale_uploads()
    logger.info("Marked %d stale uploads as failed", updated)


async def publish_archive_maintenance_jobs() -> None:
    requeued_indexing = await requeue_stale_indexing_jobs(startup=False)
    requeued_enrichment = await requeue_stale_enrichment_jobs(startup=False)
    logger.info(
        "Archive maintenance tick requeued %d indexing jobs and %d enrichment jobs",
        requeued_indexing,
        requeued_enrichment,
    )


async def publish_archive_sync_maintenance_jobs() -> None:
    requeued_sync = await requeue_stale_sync_runs(startup=False)
    refreshed_sync = await refresh_active_sync_run_statuses()
    refreshed_enrichment = await refresh_active_enrichment_run_statuses()
    logger.info(
        "Archive sync control tick requeued %d sync runs, refreshed %d sync runs, refreshed %d enrichment runs",
        requeued_sync,
        refreshed_sync,
        refreshed_enrichment,
    )


async def publish_archive_startup_recovery_job() -> None:
    recovered_indexing = await requeue_stale_indexing_jobs(startup=True)
    recovered_enrichment = await requeue_stale_enrichment_jobs(startup=True)
    recovered_sync = await requeue_stale_sync_runs(startup=True)
    logger.info(
        "Archive startup recovery requeued %d indexing jobs, %d enrichment jobs, %d sync runs",
        recovered_indexing,
        recovered_enrichment,
        recovered_sync,
    )


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    await publish_archive_startup_recovery_job()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(publish_cleanup_job, "interval", minutes=10)
    scheduler.add_job(publish_archive_sync_maintenance_jobs, "interval", minutes=1)
    scheduler.add_job(publish_archive_maintenance_jobs, "interval", minutes=15)
    scheduler.start()
    logger.info("Scheduler started")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

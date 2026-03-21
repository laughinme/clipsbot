import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def init_scheduler(settings: Settings | None = None) -> AsyncIOScheduler | None:
    settings = settings or get_settings()
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled")
        return None

    scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 30,
        },
    )

    scheduler.start()
    logger.info("Scheduler started")
    return scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None) -> None:
    if scheduler is None:
        return

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

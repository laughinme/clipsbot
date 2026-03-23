from __future__ import annotations

import asyncio
import json
import logging

from aio_pika import DeliveryMode, Message, connect_robust
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from broker import MAINTENANCE_QUEUE, ensure_topology
from core.config import configure_logging, get_settings


logger = logging.getLogger(__name__)


async def publish_cleanup_job() -> None:
    settings = get_settings()
    connection = await connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await ensure_topology(channel)
        body = json.dumps({"task": "clips.cleanup_stale_uploads"}).encode("utf-8")
        await channel.default_exchange.publish(
            Message(
                body=body,
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
            ),
            routing_key=MAINTENANCE_QUEUE,
        )
    logger.info("Published maintenance cleanup job")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(publish_cleanup_job, "interval", minutes=10)
    scheduler.start()
    logger.info("Scheduler started")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

from __future__ import annotations

from aio_pika import Channel, ExchangeType


CLIPS_EVENTS_EXCHANGE = "clips.events"
CLIPS_DLX = "clips.events.dlx"
CLIPS_PROCESS_QUEUE = "clips.process"
CLIPS_DLQ = "clips.process.dlq"
NOTIFICATIONS_QUEUE = "notifications.send"
MAINTENANCE_QUEUE = "maintenance.jobs"


async def ensure_topology(channel: Channel) -> None:
    events_exchange = await channel.declare_exchange(
        CLIPS_EVENTS_EXCHANGE,
        ExchangeType.TOPIC,
        durable=True,
    )
    dlx_exchange = await channel.declare_exchange(
        CLIPS_DLX,
        ExchangeType.DIRECT,
        durable=True,
    )

    process_queue = await channel.declare_queue(
        CLIPS_PROCESS_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": CLIPS_DLX},
    )
    await process_queue.bind(events_exchange, routing_key="clip.uploaded")

    clips_dlq = await channel.declare_queue(CLIPS_DLQ, durable=True)
    await clips_dlq.bind(dlx_exchange, routing_key=CLIPS_PROCESS_QUEUE)

    await channel.declare_queue(NOTIFICATIONS_QUEUE, durable=True)
    await channel.declare_queue(MAINTENANCE_QUEUE, durable=True)

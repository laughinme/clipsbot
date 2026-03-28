from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from aio_pika import DeliveryMode, Message, connect_robust
from fastapi import Depends

from core.config import Settings, get_settings
from .topology import CLIPS_EVENTS_EXCHANGE, ensure_topology


class BrokerPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def publish_event(self, routing_key: str, payload: dict[str, Any]) -> None:
        if not self.settings.RABBITMQ_ENABLED:
            return

        connection = await connect_robust(
            self.settings.RABBITMQ_URL,
            heartbeat=self.settings.RABBITMQ_HEARTBEAT_SEC,
        )
        async with connection:
            channel = await connection.channel()
            await ensure_topology(channel)
            exchange = await channel.get_exchange(CLIPS_EVENTS_EXCHANGE, ensure=False)
            body = json.dumps(payload).encode("utf-8")
            await exchange.publish(
                Message(
                    body=body,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
            )

    async def publish_queue_message(self, queue_name: str, payload: dict[str, Any]) -> None:
        await self.publish_queue_messages(queue_name, [payload])

    async def publish_queue_messages(
        self,
        queue_name: str,
        payloads: list[dict[str, Any]],
    ) -> None:
        if not self.settings.RABBITMQ_ENABLED or not payloads:
            return

        connection = await connect_robust(
            self.settings.RABBITMQ_URL,
            heartbeat=self.settings.RABBITMQ_HEARTBEAT_SEC,
        )
        async with connection:
            channel = await connection.channel()
            await ensure_topology(channel)
            for payload in payloads:
                body = json.dumps(payload).encode("utf-8")
                await channel.default_exchange.publish(
                    Message(
                        body=body,
                        content_type="application/json",
                        delivery_mode=DeliveryMode.PERSISTENT,
                    ),
                    routing_key=queue_name,
                )


def get_broker_publisher(
    settings: Settings = Depends(get_settings),
) -> BrokerPublisher:
    return BrokerPublisher(settings)

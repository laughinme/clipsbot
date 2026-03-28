from __future__ import annotations

from collections import Counter
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .archive_messages_table import TelegramMessage


class TelegramMessageInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, message: TelegramMessage) -> TelegramMessage:
        self.session.add(message)
        return message

    async def get_by_id(self, message_id: UUID | str) -> TelegramMessage | None:
        stmt = (
            select(TelegramMessage)
            .options(selectinload(TelegramMessage.media_asset))
            .where(TelegramMessage.id == message_id)
        )
        return await self.session.scalar(stmt)

    async def get_by_import_and_telegram_message_id(
        self,
        import_id: UUID | str,
        telegram_message_id: int,
    ) -> TelegramMessage | None:
        stmt = select(TelegramMessage).where(
            TelegramMessage.import_id == import_id,
            TelegramMessage.telegram_message_id == telegram_message_id,
        )
        return await self.session.scalar(stmt)

    async def get_by_qdrant_point_id(self, qdrant_point_id: str) -> TelegramMessage | None:
        stmt = select(TelegramMessage).where(TelegramMessage.qdrant_point_id == qdrant_point_id)
        return await self.session.scalar(stmt)

    async def list_by_ids(self, ids: list[UUID | str]) -> list[TelegramMessage]:
        if not ids:
            return []
        stmt = (
            select(TelegramMessage)
            .options(selectinload(TelegramMessage.media_asset))
            .where(TelegramMessage.id.in_(ids))
        )
        rows = await self.session.scalars(stmt)
        found = list(rows.all())
        by_id = {message.id: message for message in found}
        return [by_id[id_] for id_ in ids if id_ in by_id]

    async def count_by_import_and_status(self, import_id: UUID | str) -> dict[str, int]:
        rows = await self.session.execute(
            select(TelegramMessage.index_status, func.count(TelegramMessage.id))
            .where(TelegramMessage.import_id == import_id)
            .group_by(TelegramMessage.index_status)
        )
        return {str(status): int(count) for status, count in rows.all()}

    async def count_all_by_import(self, import_id: UUID | str) -> int:
        result = await self.session.scalar(
            select(func.count(TelegramMessage.id)).where(TelegramMessage.import_id == import_id)
        )
        return int(result or 0)

    async def bulk_requeue_processing(self, *, message_ids: list[UUID | str]) -> None:
        if not message_ids:
            return
        await self.session.execute(
            update(TelegramMessage)
            .where(
                TelegramMessage.id.in_(message_ids),
                TelegramMessage.index_status == "processing",
            )
            .values(
                index_status="queued",
                index_error=None,
            )
        )

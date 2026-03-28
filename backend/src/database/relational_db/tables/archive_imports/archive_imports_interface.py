from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .archive_imports_table import TelegramImport


class TelegramImportInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, telegram_import: TelegramImport) -> TelegramImport:
        self.session.add(telegram_import)
        return telegram_import

    async def get_by_id(self, import_id: UUID | str) -> TelegramImport | None:
        return await self.session.scalar(select(TelegramImport).where(TelegramImport.id == import_id))

    async def get_by_manifest_sha256(self, manifest_sha256: str) -> TelegramImport | None:
        return await self.session.scalar(
            select(TelegramImport).where(TelegramImport.manifest_sha256 == manifest_sha256)
        )

    async def list_recent(self, *, limit: int = 10) -> list[TelegramImport]:
        rows = await self.session.scalars(
            select(TelegramImport).order_by(TelegramImport.created_at.desc()).limit(limit)
        )
        return list(rows.all())

    async def list_stuck_by_status(
        self,
        *,
        status: str,
        older_than_minutes: int = 60,
    ) -> list[TelegramImport]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.scalars(
            select(TelegramImport).where(
                TelegramImport.status == status,
                TelegramImport.updated_at < threshold,
            )
        )
        return list(rows.all())

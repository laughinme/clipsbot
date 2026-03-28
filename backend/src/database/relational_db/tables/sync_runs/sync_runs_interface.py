from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .sync_runs_table import SyncRun


class SyncRunInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, sync_run: SyncRun) -> SyncRun:
        self.session.add(sync_run)
        return sync_run

    async def get_by_id(self, sync_run_id: UUID | str) -> SyncRun | None:
        return await self.session.scalar(select(SyncRun).where(SyncRun.id == sync_run_id))

    async def list_by_source(self, source_id: UUID | str, *, limit: int = 20) -> list[SyncRun]:
        rows = await self.session.scalars(
            select(SyncRun)
            .where(SyncRun.source_id == source_id)
            .order_by(desc(SyncRun.created_at))
            .limit(limit)
        )
        return list(rows.all())

    async def list_stuck_by_status(self, *, status: str, older_than_minutes: int) -> list[SyncRun]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.scalars(
            select(SyncRun).where(
                SyncRun.status == status,
                SyncRun.updated_at < threshold,
            )
        )
        return list(rows.all())

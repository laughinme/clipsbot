from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .enrichment_runs_table import EnrichmentRun


class EnrichmentRunInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, enrichment_run: EnrichmentRun) -> EnrichmentRun:
        self.session.add(enrichment_run)
        return enrichment_run

    async def get_by_id(self, enrichment_run_id: UUID | str) -> EnrichmentRun | None:
        return await self.session.scalar(select(EnrichmentRun).where(EnrichmentRun.id == enrichment_run_id))

    async def get_by_sync_run(self, sync_run_id: UUID | str) -> EnrichmentRun | None:
        return await self.session.scalar(select(EnrichmentRun).where(EnrichmentRun.sync_run_id == sync_run_id))

    async def list_by_source(self, source_id: UUID | str, *, limit: int = 20) -> list[EnrichmentRun]:
        rows = await self.session.scalars(
            select(EnrichmentRun)
            .where(EnrichmentRun.source_id == source_id)
            .order_by(desc(EnrichmentRun.created_at))
            .limit(limit)
        )
        return list(rows.all())

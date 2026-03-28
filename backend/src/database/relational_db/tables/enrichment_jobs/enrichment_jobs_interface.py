from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..corpus_assets import CorpusAsset
from ..corpus_enrichments import CorpusEnrichment
from ..corpus_items import CorpusItem
from ..corpus_projections import CorpusProjection
from .enrichment_jobs_table import EnrichmentJob


class EnrichmentJobInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, job: EnrichmentJob) -> EnrichmentJob:
        self.session.add(job)
        return job

    async def get_by_id(self, job_id: UUID | str) -> EnrichmentJob | None:
        stmt = (
            select(EnrichmentJob)
            .options(
                selectinload(EnrichmentJob.enrichment_run),
                selectinload(EnrichmentJob.corpus_item).selectinload(CorpusItem.source),
                selectinload(EnrichmentJob.corpus_item).selectinload(CorpusItem.assets),
                selectinload(EnrichmentJob.corpus_item).selectinload(CorpusItem.enrichments),
                selectinload(EnrichmentJob.corpus_item).selectinload(CorpusItem.projections),
            )
            .where(EnrichmentJob.id == job_id)
        )
        return await self.session.scalar(stmt)

    async def get_active_for_run_item_kind(
        self,
        enrichment_run_id: UUID | str,
        corpus_item_id: UUID | str,
        enrichment_kind: str,
    ) -> EnrichmentJob | None:
        return await self.session.scalar(
            select(EnrichmentJob).where(
                EnrichmentJob.enrichment_run_id == enrichment_run_id,
                EnrichmentJob.corpus_item_id == corpus_item_id,
                EnrichmentJob.enrichment_kind == enrichment_kind,
                EnrichmentJob.status.in_(("queued", "processing")),
            )
        )

    async def get_for_run_item_kind(
        self,
        enrichment_run_id: UUID | str,
        corpus_item_id: UUID | str,
        enrichment_kind: str,
    ) -> EnrichmentJob | None:
        return await self.session.scalar(
            select(EnrichmentJob).where(
                EnrichmentJob.enrichment_run_id == enrichment_run_id,
                EnrichmentJob.corpus_item_id == corpus_item_id,
                EnrichmentJob.enrichment_kind == enrichment_kind,
            )
        )

    async def list_for_run(self, enrichment_run_id: UUID | str) -> list[EnrichmentJob]:
        rows = await self.session.scalars(
            select(EnrichmentJob)
            .where(EnrichmentJob.enrichment_run_id == enrichment_run_id)
            .order_by(EnrichmentJob.created_at.asc())
        )
        return list(rows.all())

    async def list_stuck_processing(self, *, older_than_minutes: int = 30) -> list[EnrichmentJob]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.scalars(
            select(EnrichmentJob).where(
                EnrichmentJob.status == "processing",
                EnrichmentJob.started_at.is_not(None),
                EnrichmentJob.started_at < threshold,
            )
        )
        return list(rows.all())

    async def bulk_requeue_processing(
        self,
        *,
        older_than_minutes: int,
        last_error: str,
    ) -> list[tuple[UUID, UUID, str, UUID]]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.execute(
            select(
                EnrichmentJob.id,
                EnrichmentJob.corpus_item_id,
                EnrichmentJob.enrichment_kind,
                EnrichmentJob.enrichment_run_id,
            ).where(
                EnrichmentJob.status == "processing",
                EnrichmentJob.started_at.is_not(None),
                EnrichmentJob.started_at < threshold,
            )
        )
        items = [(job_id, corpus_item_id, enrichment_kind, enrichment_run_id) for job_id, corpus_item_id, enrichment_kind, enrichment_run_id in rows.all()]
        if not items:
            return []
        job_ids = [job_id for job_id, _, _, _ in items]
        await self.session.execute(
            update(EnrichmentJob)
            .where(EnrichmentJob.id.in_(job_ids))
            .values(
                status="queued",
                started_at=None,
                last_error=last_error,
            )
        )
        return items

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..corpus_items import CorpusItem
from ..corpus_projections import CorpusProjection
from .indexing_jobs_table import IndexingJob


class IndexingJobInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _with_related(self, stmt):
        return stmt.options(
            selectinload(IndexingJob.projection)
            .selectinload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.source),
            selectinload(IndexingJob.projection)
            .selectinload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.assets),
            selectinload(IndexingJob.projection)
            .selectinload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.enrichments),
            selectinload(IndexingJob.sync_run),
        )

    async def add(self, job: IndexingJob) -> IndexingJob:
        self.session.add(job)
        return job

    async def get_by_id(self, job_id: UUID | str) -> IndexingJob | None:
        stmt = self._with_related(select(IndexingJob)).where(IndexingJob.id == job_id)
        return await self.session.scalar(stmt)

    async def list_by_ids(self, job_ids: list[UUID | str]) -> list[IndexingJob]:
        if not job_ids:
            return []
        stmt = self._with_related(select(IndexingJob)).where(IndexingJob.id.in_(job_ids))
        rows = await self.session.scalars(stmt)
        found = list(rows.all())
        by_id = {job.id: job for job in found}
        return [by_id[job_id] for job_id in job_ids if job_id in by_id]

    async def get_active_for_projection(self, projection_id: UUID | str) -> IndexingJob | None:
        stmt = (
            select(IndexingJob)
            .where(
                IndexingJob.projection_id == projection_id,
                IndexingJob.status.in_(("queued", "processing")),
            )
            .order_by(IndexingJob.created_at.desc())
        )
        return await self.session.scalar(stmt)

    async def list_queued_for_sync_run(self, sync_run_id: UUID | str, *, limit: int) -> list[IndexingJob]:
        rows = await self.session.scalars(
            select(IndexingJob)
            .where(
                IndexingJob.sync_run_id == sync_run_id,
                IndexingJob.status == "queued",
            )
            .order_by(IndexingJob.created_at.asc())
            .limit(limit)
        )
        return list(rows.all())

    async def list_for_sync_run(self, sync_run_id: UUID | str) -> list[IndexingJob]:
        rows = await self.session.scalars(
            select(IndexingJob)
            .where(IndexingJob.sync_run_id == sync_run_id)
            .order_by(IndexingJob.created_at.asc())
        )
        return list(rows.all())

    async def list_stuck_processing(self, *, older_than_minutes: int = 30) -> list[IndexingJob]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.scalars(
            select(IndexingJob).where(
                IndexingJob.status == "processing",
                IndexingJob.started_at.is_not(None),
                IndexingJob.started_at < threshold,
            )
        )
        return list(rows.all())

    async def bulk_requeue_processing(
        self,
        *,
        older_than_minutes: int,
        last_error: str,
    ) -> list[tuple[UUID, UUID, UUID]]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.execute(
            select(IndexingJob.id, IndexingJob.projection_id, IndexingJob.sync_run_id).where(
                IndexingJob.status == "processing",
                IndexingJob.started_at.is_not(None),
                IndexingJob.started_at < threshold,
            )
        )
        items = [(job_id, projection_id, sync_run_id) for job_id, projection_id, sync_run_id in rows.all()]
        if not items:
            return []
        job_ids = [job_id for job_id, _, _ in items]
        await self.session.execute(
            update(IndexingJob)
            .where(IndexingJob.id.in_(job_ids))
            .values(
                status="queued",
                started_at=None,
                last_error=last_error,
            )
        )
        return items

    async def claim_additional_text_batch(
        self,
        *,
        projection_kind: str,
        limit: int,
        exclude_job_ids: list[UUID | str],
        raw_text_only: bool,
    ) -> list[IndexingJob]:
        if limit <= 0:
            return []

        stmt = (
            select(IndexingJob.id)
            .join(IndexingJob.projection)
            .join(CorpusProjection.corpus_item)
            .where(
                IndexingJob.status == "queued",
                CorpusProjection.projection_kind == projection_kind,
            )
            .order_by(IndexingJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if exclude_job_ids:
            stmt = stmt.where(IndexingJob.id.not_in(exclude_job_ids))
        if raw_text_only:
            stmt = stmt.where(CorpusItem.content_type == "text")

        rows = await self.session.execute(stmt)
        job_ids = [job_id for (job_id,) in rows.all()]
        if not job_ids:
            return []

        started_at = datetime.now(UTC)
        await self.session.execute(
            update(IndexingJob)
            .where(IndexingJob.id.in_(job_ids))
            .values(
                status="processing",
                started_at=started_at,
                attempts=IndexingJob.attempts + 1,
            )
        )
        return await self.list_by_ids(job_ids)

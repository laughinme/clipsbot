from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..archive_messages import TelegramMessage
from .embedding_jobs_table import EmbeddingJob


class EmbeddingJobInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, job: EmbeddingJob) -> EmbeddingJob:
        self.session.add(job)
        return job

    async def get_by_id(self, job_id: UUID | str) -> EmbeddingJob | None:
        return await self.session.scalar(select(EmbeddingJob).where(EmbeddingJob.id == job_id))

    async def get_by_message_id(self, message_id: UUID | str) -> EmbeddingJob | None:
        return await self.session.scalar(select(EmbeddingJob).where(EmbeddingJob.message_id == message_id))

    async def claim_queued_text_batch(
        self,
        *,
        import_id: UUID | str,
        seed_job_id: UUID | str,
        limit: int,
    ) -> list[EmbeddingJob]:
        priority = case((EmbeddingJob.id == seed_job_id, 0), else_=1)
        rows = await self.session.scalars(
            select(EmbeddingJob)
            .options(selectinload(EmbeddingJob.message))
            .join(TelegramMessage, TelegramMessage.id == EmbeddingJob.message_id)
            .where(
                EmbeddingJob.import_id == import_id,
                EmbeddingJob.status == "queued",
                TelegramMessage.message_type == "text",
                TelegramMessage.index_status == "queued",
            )
            .order_by(priority, EmbeddingJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(rows.all())

    async def claim_queued_media_batch(
        self,
        *,
        import_id: UUID | str,
        seed_job_id: UUID | str,
        message_type: str,
        limit: int,
    ) -> list[EmbeddingJob]:
        priority = case((EmbeddingJob.id == seed_job_id, 0), else_=1)
        rows = await self.session.scalars(
            select(EmbeddingJob)
            .options(selectinload(EmbeddingJob.message))
            .join(TelegramMessage, TelegramMessage.id == EmbeddingJob.message_id)
            .where(
                EmbeddingJob.import_id == import_id,
                EmbeddingJob.status == "queued",
                TelegramMessage.message_type == message_type,
                TelegramMessage.index_status == "queued",
            )
            .order_by(priority, TelegramMessage.timestamp.asc(), EmbeddingJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(rows.all())

    async def list_stuck_processing(self, *, older_than_minutes: int = 30) -> list[EmbeddingJob]:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        rows = await self.session.scalars(
            select(EmbeddingJob).where(
                EmbeddingJob.status == "processing",
                EmbeddingJob.started_at.is_not(None),
                EmbeddingJob.started_at < threshold,
            )
        )
        return list(rows.all())

    async def list_queued_for_import(
        self,
        *,
        import_id: UUID | str,
        limit: int,
    ) -> list[EmbeddingJob]:
        type_priority = case(
            (TelegramMessage.message_type == "text", 0),
            (TelegramMessage.message_type == "photo", 1),
            (TelegramMessage.message_type == "voice", 2),
            else_=3,
        )
        rows = await self.session.scalars(
            select(EmbeddingJob)
            .options(selectinload(EmbeddingJob.message))
            .join(TelegramMessage, TelegramMessage.id == EmbeddingJob.message_id)
            .where(
                EmbeddingJob.import_id == import_id,
                EmbeddingJob.status == "queued",
                TelegramMessage.index_status == "queued",
            )
            .order_by(type_priority, TelegramMessage.timestamp.asc(), EmbeddingJob.created_at.asc())
            .limit(limit)
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
            select(EmbeddingJob.id, EmbeddingJob.message_id, EmbeddingJob.import_id).where(
                EmbeddingJob.status == "processing",
                EmbeddingJob.started_at.is_not(None),
                EmbeddingJob.started_at < threshold,
            )
        )
        items = [(job_id, message_id, import_id) for job_id, message_id, import_id in rows.all()]
        if not items:
            return []
        job_ids = [job_id for job_id, _, _ in items]
        await self.session.execute(
            update(EmbeddingJob)
            .where(EmbeddingJob.id.in_(job_ids))
            .values(
                status="queued",
                started_at=None,
                last_error=last_error,
            )
        )
        return items

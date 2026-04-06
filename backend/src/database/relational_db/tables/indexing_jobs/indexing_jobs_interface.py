from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ..corpus_assets import CorpusAsset
from ..corpus_items import CorpusItem
from ..corpus_projections import CorpusProjection
from ..source_connections import SourceConnection
from .indexing_jobs_table import IndexingJob


@dataclass(slots=True)
class ProcessingSourceSnapshot:
    kind: str
    display_name: str


@dataclass(slots=True)
class ProcessingAssetSnapshot:
    id: UUID
    role: str
    storage_bucket: str
    object_key: str
    source_relative_path: str | None
    original_filename: str | None
    mime_type: str | None
    duration_ms: int | None
    width: int | None
    height: int | None


@dataclass(slots=True)
class ProcessingItemSnapshot:
    id: UUID
    source_id: UUID
    stable_key: str
    content_type: str
    occurred_at: datetime
    author_external_id: str | None
    author_name: str | None
    container_external_id: str | None
    container_name: str | None
    text_content: str | None
    caption: str | None
    present_in_latest_sync: bool
    source: ProcessingSourceSnapshot
    assets: list[ProcessingAssetSnapshot] = field(default_factory=list)
    enrichments: list = field(default_factory=list)


@dataclass(slots=True)
class ProcessingProjectionSnapshot:
    id: UUID
    projection_kind: str
    corpus_item: ProcessingItemSnapshot
    qdrant_point_id: str | None = None


@dataclass(slots=True)
class ProcessingJobSnapshot:
    id: UUID
    status: str
    projection: ProcessingProjectionSnapshot
    attempts: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None


class IndexingJobInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _with_related(self, stmt, *, include_enrichments: bool, include_sync_run: bool):
        options = [
            selectinload(IndexingJob.projection)
            .selectinload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.source),
            selectinload(IndexingJob.projection)
            .selectinload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.assets),
        ]
        if include_enrichments:
            options.append(
                selectinload(IndexingJob.projection)
                .selectinload(CorpusProjection.corpus_item)
                .selectinload(CorpusItem.enrichments)
            )
        if include_sync_run:
            options.append(selectinload(IndexingJob.sync_run))
        return stmt.options(*options)

    def _with_related_for_processing(self, stmt, *, include_enrichments: bool):
        options = [
            joinedload(IndexingJob.projection)
            .joinedload(CorpusProjection.corpus_item)
            .joinedload(CorpusItem.source),
            joinedload(IndexingJob.projection)
            .joinedload(CorpusProjection.corpus_item)
            .selectinload(CorpusItem.assets),
        ]
        if include_enrichments:
            options.append(
                joinedload(IndexingJob.projection)
                .joinedload(CorpusProjection.corpus_item)
                .selectinload(CorpusItem.enrichments)
            )
        return stmt.options(*options)

    async def add(self, job: IndexingJob) -> IndexingJob:
        self.session.add(job)
        return job

    async def get_by_id(
        self,
        job_id: UUID | str,
        *,
        include_enrichments: bool = False,
        include_sync_run: bool = False,
    ) -> IndexingJob | None:
        stmt = self._with_related(
            select(IndexingJob),
            include_enrichments=include_enrichments,
            include_sync_run=include_sync_run,
        ).where(IndexingJob.id == job_id)
        return await self.session.scalar(stmt)

    async def get_by_id_for_processing(
        self,
        job_id: UUID | str,
        *,
        include_enrichments: bool = False,
    ) -> IndexingJob | None:
        stmt = self._with_related_for_processing(
            select(IndexingJob),
            include_enrichments=include_enrichments,
        ).where(IndexingJob.id == job_id)
        return await self.session.scalar(stmt)

    async def get_processing_snapshot(self, job_id: UUID | str) -> ProcessingJobSnapshot | None:
        row = (
            await self.session.execute(
                select(
                    IndexingJob.id.label("job_id"),
                    IndexingJob.status.label("job_status"),
                    IndexingJob.attempts.label("job_attempts"),
                    IndexingJob.started_at.label("job_started_at"),
                    IndexingJob.completed_at.label("job_completed_at"),
                    IndexingJob.last_error.label("job_last_error"),
                    CorpusProjection.id.label("projection_id"),
                    CorpusProjection.projection_kind.label("projection_kind"),
                    CorpusProjection.qdrant_point_id.label("projection_qdrant_point_id"),
                    CorpusItem.id.label("item_id"),
                    CorpusItem.source_id.label("item_source_id"),
                    CorpusItem.stable_key.label("item_stable_key"),
                    CorpusItem.content_type.label("item_content_type"),
                    CorpusItem.occurred_at.label("item_occurred_at"),
                    CorpusItem.author_external_id.label("item_author_external_id"),
                    CorpusItem.author_name.label("item_author_name"),
                    CorpusItem.container_external_id.label("item_container_external_id"),
                    CorpusItem.container_name.label("item_container_name"),
                    CorpusItem.text_content.label("item_text_content"),
                    CorpusItem.caption.label("item_caption"),
                    CorpusItem.present_in_latest_sync.label("item_present_in_latest_sync"),
                    SourceConnection.kind.label("source_kind"),
                    SourceConnection.display_name.label("source_display_name"),
                    CorpusAsset.id.label("asset_id"),
                    CorpusAsset.role.label("asset_role"),
                    CorpusAsset.storage_bucket.label("asset_storage_bucket"),
                    CorpusAsset.object_key.label("asset_object_key"),
                    CorpusAsset.source_relative_path.label("asset_source_relative_path"),
                    CorpusAsset.original_filename.label("asset_original_filename"),
                    CorpusAsset.mime_type.label("asset_mime_type"),
                    CorpusAsset.duration_ms.label("asset_duration_ms"),
                    CorpusAsset.width.label("asset_width"),
                    CorpusAsset.height.label("asset_height"),
                )
                .join(IndexingJob.projection)
                .join(CorpusProjection.corpus_item)
                .join(CorpusItem.source)
                .outerjoin(
                    CorpusAsset,
                    and_(
                        CorpusAsset.corpus_item_id == CorpusItem.id,
                        CorpusAsset.role == "primary",
                    ),
                )
                .where(IndexingJob.id == job_id)
            )
        ).mappings().first()
        if row is None:
            return None

        source = ProcessingSourceSnapshot(
            kind=row["source_kind"],
            display_name=row["source_display_name"],
        )
        item = ProcessingItemSnapshot(
            id=row["item_id"],
            source_id=row["item_source_id"],
            stable_key=row["item_stable_key"],
            content_type=row["item_content_type"],
            occurred_at=row["item_occurred_at"],
            author_external_id=row["item_author_external_id"],
            author_name=row["item_author_name"],
            container_external_id=row["item_container_external_id"],
            container_name=row["item_container_name"],
            text_content=row["item_text_content"],
            caption=row["item_caption"],
            present_in_latest_sync=bool(row["item_present_in_latest_sync"]),
            source=source,
        )
        if row["asset_id"] is not None:
            item.assets.append(
                ProcessingAssetSnapshot(
                    id=row["asset_id"],
                    role=row["asset_role"],
                    storage_bucket=row["asset_storage_bucket"],
                    object_key=row["asset_object_key"],
                    source_relative_path=row["asset_source_relative_path"],
                    original_filename=row["asset_original_filename"],
                    mime_type=row["asset_mime_type"],
                    duration_ms=row["asset_duration_ms"],
                    width=row["asset_width"],
                    height=row["asset_height"],
                )
            )

        projection = ProcessingProjectionSnapshot(
            id=row["projection_id"],
            projection_kind=row["projection_kind"],
            corpus_item=item,
            qdrant_point_id=row["projection_qdrant_point_id"],
        )
        return ProcessingJobSnapshot(
            id=row["job_id"],
            status=row["job_status"],
            attempts=int(row["job_attempts"] or 0),
            started_at=row["job_started_at"],
            completed_at=row["job_completed_at"],
            last_error=row["job_last_error"],
            projection=projection,
        )

    async def list_by_ids(
        self,
        job_ids: list[UUID | str],
        *,
        include_enrichments: bool = True,
        include_sync_run: bool = False,
    ) -> list[IndexingJob]:
        if not job_ids:
            return []
        stmt = self._with_related(
            select(IndexingJob),
            include_enrichments=include_enrichments,
            include_sync_run=include_sync_run,
        ).where(IndexingJob.id.in_(job_ids))
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

    async def claim_for_sync_run(
        self,
        sync_run_id: UUID | str,
        *,
        limit: int,
        prioritize_types: bool = True,
        content_types: list[str] | None = None,
    ) -> list[IndexingJob]:
        if limit <= 0:
            return []

        stmt = (
            select(IndexingJob.id)
            .join(IndexingJob.projection)
            .join(CorpusProjection.corpus_item)
            .where(
                IndexingJob.sync_run_id == sync_run_id,
                IndexingJob.status == "queued",
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if content_types:
            stmt = stmt.where(CorpusItem.content_type.in_(content_types))
        if prioritize_types:
            priority = case(
                (CorpusItem.content_type == "text", 0),
                (CorpusItem.content_type == "photo", 1),
                (CorpusItem.content_type == "voice", 2),
                (CorpusItem.content_type == "audio", 3),
                (CorpusItem.content_type == "video", 4),
                else_=5,
            )
            stmt = stmt.order_by(priority.asc(), IndexingJob.created_at.asc())
        else:
            stmt = stmt.order_by(IndexingJob.created_at.asc())
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
        return await self.list_by_ids(
            job_ids,
            include_enrichments=False,
            include_sync_run=False,
        )

    async def get_next_queued_content_type(self, sync_run_id: UUID | str) -> str | None:
        priority = case(
            (CorpusItem.content_type == "text", 0),
            (CorpusItem.content_type == "photo", 1),
            (CorpusItem.content_type == "voice", 2),
            (CorpusItem.content_type == "audio", 3),
            (CorpusItem.content_type == "video", 4),
            else_=5,
        )
        row = await self.session.execute(
            select(CorpusItem.content_type)
            .join(IndexingJob.projection)
            .join(CorpusProjection.corpus_item)
            .where(
                IndexingJob.sync_run_id == sync_run_id,
                IndexingJob.status == "queued",
            )
            .order_by(priority.asc(), IndexingJob.created_at.asc())
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def list_for_sync_run(self, sync_run_id: UUID | str) -> list[IndexingJob]:
        rows = await self.session.scalars(
            select(IndexingJob)
            .where(IndexingJob.sync_run_id == sync_run_id)
            .order_by(IndexingJob.created_at.asc())
        )
        return list(rows.all())

    async def get_sync_run_status_counts(self, sync_run_id: UUID | str) -> dict[str, int]:
        queued_expr = func.sum(case((IndexingJob.status == "queued", 1), else_=0))
        processing_expr = func.sum(case((IndexingJob.status == "processing", 1), else_=0))
        done_expr = func.sum(case((IndexingJob.status == "done", 1), else_=0))
        failed_expr = func.sum(case((IndexingJob.status == "failed", 1), else_=0))

        row = await self.session.execute(
            select(
                queued_expr.label("queued_items"),
                processing_expr.label("processing_items"),
                done_expr.label("indexed_items"),
                failed_expr.label("failed_items"),
            ).where(IndexingJob.sync_run_id == sync_run_id)
        )
        data = row.one()
        return {
            "queued_items": int(data.queued_items or 0),
            "processing_items": int(data.processing_items or 0),
            "indexed_items": int(data.indexed_items or 0),
            "failed_items": int(data.failed_items or 0),
        }

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

    async def list_processing_for_sync_run(self, sync_run_id: UUID | str) -> list[tuple[UUID, datetime | None]]:
        rows = await self.session.execute(
            select(IndexingJob.id, IndexingJob.started_at).where(
                IndexingJob.sync_run_id == sync_run_id,
                IndexingJob.status == "processing",
            )
        )
        return [(job_id, started_at) for job_id, started_at in rows.all()]

    async def mark_done_fast(
        self,
        *,
        job_id: UUID | str,
        projection_id: UUID | str,
        point_id: str,
        embedding_model: str,
    ) -> None:
        completed_at = datetime.now(UTC)
        await self.session.execute(
            update(CorpusProjection)
            .where(CorpusProjection.id == projection_id)
            .values(
                qdrant_point_id=point_id,
                index_status="indexed",
                index_error=None,
                embedding_model=embedding_model,
            )
        )
        await self.session.execute(
            update(IndexingJob)
            .where(IndexingJob.id == job_id)
            .values(
                status="done",
                completed_at=completed_at,
                last_error=None,
            )
        )

    async def mark_failed_fast(
        self,
        *,
        job_id: UUID | str,
        projection_id: UUID | str,
        error: str,
    ) -> None:
        completed_at = datetime.now(UTC)
        await self.session.execute(
            update(CorpusProjection)
            .where(CorpusProjection.id == projection_id)
            .values(
                index_status="failed",
                index_error=error,
            )
        )
        await self.session.execute(
            update(IndexingJob)
            .where(IndexingJob.id == job_id)
            .values(
                status="failed",
                completed_at=completed_at,
                last_error=error,
            )
        )

    async def bulk_requeue_job_ids(
        self,
        job_ids: list[UUID | str],
        *,
        last_error: str,
    ) -> int:
        if not job_ids:
            return 0
        result = await self.session.execute(
            update(IndexingJob)
            .where(
                IndexingJob.id.in_(job_ids),
                IndexingJob.status == "processing",
            )
            .values(
                status="queued",
                started_at=None,
                last_error=last_error,
            )
        )
        return int(result.rowcount or 0)

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

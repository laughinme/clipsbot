from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..corpus_items import CorpusItem
from .corpus_projections_table import CorpusProjection


class CorpusProjectionInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, projection: CorpusProjection) -> CorpusProjection:
        self.session.add(projection)
        return projection

    async def get_by_id(self, projection_id: UUID | str) -> CorpusProjection | None:
        stmt = (
            select(CorpusProjection)
            .options(
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.source),
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.assets),
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.enrichments),
            )
            .where(CorpusProjection.id == projection_id)
        )
        return await self.session.scalar(stmt)

    async def get_by_corpus_item_and_kind(
        self,
        corpus_item_id: UUID | str,
        projection_kind: str,
    ) -> CorpusProjection | None:
        return await self.session.scalar(
            select(CorpusProjection)
            .options(
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.source),
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.assets),
                selectinload(CorpusProjection.corpus_item).selectinload(CorpusItem.enrichments),
            )
            .where(
                CorpusProjection.corpus_item_id == corpus_item_id,
                CorpusProjection.projection_kind == projection_kind,
            )
        )

    async def get_by_qdrant_point_id(self, qdrant_point_id: str) -> CorpusProjection | None:
        return await self.session.scalar(
            select(CorpusProjection).where(CorpusProjection.qdrant_point_id == qdrant_point_id)
        )

    async def list_by_corpus_item_ids_and_kind(
        self,
        corpus_item_ids: list[UUID | str],
        projection_kind: str,
    ) -> dict[UUID, CorpusProjection]:
        normalized_ids = [projection_id for projection_id in dict.fromkeys(corpus_item_ids) if projection_id]
        if not normalized_ids:
            return {}
        rows = await self.session.scalars(
            select(CorpusProjection).where(
                CorpusProjection.corpus_item_id.in_(normalized_ids),
                CorpusProjection.projection_kind == projection_kind,
            )
        )
        return {projection.corpus_item_id: projection for projection in rows.all()}

    async def bulk_requeue_processing(self, *, projection_ids: list[UUID | str]) -> None:
        if not projection_ids:
            return
        await self.session.execute(
            update(CorpusProjection)
            .where(
                CorpusProjection.id.in_(projection_ids),
                CorpusProjection.index_status == "processing",
            )
            .values(
                index_status="queued",
                index_error=None,
            )
        )

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .corpus_items_table import CorpusItem


class CorpusItemInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, item: CorpusItem) -> CorpusItem:
        self.session.add(item)
        return item

    async def get_by_id(self, item_id: UUID | str) -> CorpusItem | None:
        stmt = (
            select(CorpusItem)
            .options(
                selectinload(CorpusItem.source),
                selectinload(CorpusItem.assets),
                selectinload(CorpusItem.projections),
                selectinload(CorpusItem.enrichments),
            )
            .where(CorpusItem.id == item_id)
        )
        return await self.session.scalar(stmt)

    async def get_by_source_and_external_key(
        self,
        source_id: UUID | str,
        external_key: str,
    ) -> CorpusItem | None:
        stmt = (
            select(CorpusItem)
            .options(
                selectinload(CorpusItem.assets),
                selectinload(CorpusItem.projections),
                selectinload(CorpusItem.enrichments),
            )
            .where(
                CorpusItem.source_id == source_id,
                CorpusItem.external_key == external_key,
            )
        )
        return await self.session.scalar(stmt)

    async def list_by_ids(self, ids: list[UUID | str]) -> list[CorpusItem]:
        if not ids:
            return []
        stmt = (
            select(CorpusItem)
            .options(
                selectinload(CorpusItem.source),
                selectinload(CorpusItem.assets),
                selectinload(CorpusItem.projections),
                selectinload(CorpusItem.enrichments),
            )
            .where(CorpusItem.id.in_(ids))
        )
        rows = await self.session.scalars(stmt)
        found = list(rows.all())
        by_id = {item.id: item for item in found}
        return [by_id[item_id] for item_id in ids if item_id in by_id]

    async def mark_not_seen_in_full_snapshot(
        self,
        *,
        source_id: UUID | str,
        current_run_id: UUID | str,
    ) -> int:
        result = await self.session.execute(
            update(CorpusItem)
            .where(
                CorpusItem.source_id == source_id,
                CorpusItem.present_in_latest_sync.is_(True),
                or_(
                    CorpusItem.last_seen_run_id.is_(None),
                    CorpusItem.last_seen_run_id != current_run_id,
                ),
            )
            .values(
                present_in_latest_sync=False,
                updated_at=datetime.now(UTC),
            )
        )
        return int(result.rowcount or 0)

    async def list_for_enrichment_scope(
        self,
        *,
        source_ids: list[UUID | str] | None = None,
        content_types: list[str] | None = None,
        present_in_latest_sync: bool | None = None,
    ) -> list[CorpusItem]:
        stmt = (
            select(CorpusItem)
            .options(
                selectinload(CorpusItem.source),
                selectinload(CorpusItem.assets),
                selectinload(CorpusItem.projections),
                selectinload(CorpusItem.enrichments),
            )
            .order_by(CorpusItem.occurred_at.desc())
        )
        if source_ids:
            stmt = stmt.where(CorpusItem.source_id.in_(source_ids))
        if content_types:
            stmt = stmt.where(CorpusItem.content_type.in_(content_types))
        if present_in_latest_sync is not None:
            stmt = stmt.where(CorpusItem.present_in_latest_sync.is_(present_in_latest_sync))
        rows = await self.session.scalars(stmt)
        return list(rows.all())

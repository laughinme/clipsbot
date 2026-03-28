from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .corpus_enrichments_table import CorpusEnrichment


class CorpusEnrichmentInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, enrichment: CorpusEnrichment) -> CorpusEnrichment:
        self.session.add(enrichment)
        return enrichment

    async def get_by_id(self, enrichment_id: UUID | str) -> CorpusEnrichment | None:
        return await self.session.scalar(select(CorpusEnrichment).where(CorpusEnrichment.id == enrichment_id))

    async def get_by_item_and_kind(
        self,
        corpus_item_id: UUID | str,
        enrichment_kind: str,
    ) -> CorpusEnrichment | None:
        return await self.session.scalar(
            select(CorpusEnrichment).where(
                CorpusEnrichment.corpus_item_id == corpus_item_id,
                CorpusEnrichment.enrichment_kind == enrichment_kind,
            )
        )

    async def list_by_item_ids(self, corpus_item_ids: list[UUID | str]) -> list[CorpusEnrichment]:
        if not corpus_item_ids:
            return []
        rows = await self.session.scalars(
            select(CorpusEnrichment).where(CorpusEnrichment.corpus_item_id.in_(corpus_item_ids))
        )
        return list(rows.all())

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .corpus_assets_table import CorpusAsset


class CorpusAssetInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, asset: CorpusAsset) -> CorpusAsset:
        self.session.add(asset)
        return asset

    async def get_by_id(self, asset_id: UUID | str) -> CorpusAsset | None:
        return await self.session.scalar(select(CorpusAsset).where(CorpusAsset.id == asset_id))

    async def get_by_corpus_item_and_role(
        self,
        corpus_item_id: UUID | str,
        role: str,
    ) -> CorpusAsset | None:
        return await self.session.scalar(
            select(CorpusAsset).where(
                CorpusAsset.corpus_item_id == corpus_item_id,
                CorpusAsset.role == role,
            )
        )

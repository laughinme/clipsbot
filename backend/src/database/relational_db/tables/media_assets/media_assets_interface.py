from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .media_assets_table import MediaAsset


class MediaAssetInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, asset: MediaAsset) -> MediaAsset:
        self.session.add(asset)
        return asset

    async def get_by_id(self, asset_id: UUID | str) -> MediaAsset | None:
        return await self.session.scalar(select(MediaAsset).where(MediaAsset.id == asset_id))

    async def get_by_import_and_sha256(self, import_id: UUID | str, sha256: str) -> MediaAsset | None:
        return await self.session.scalar(
            select(MediaAsset).where(MediaAsset.import_id == import_id, MediaAsset.sha256 == sha256)
        )

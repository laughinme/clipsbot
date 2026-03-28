from __future__ import annotations

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .source_connections_table import SourceConnection


class SourceConnectionInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, source: SourceConnection) -> SourceConnection:
        self.session.add(source)
        return source

    async def get_by_id(self, source_id: UUID | str) -> SourceConnection | None:
        return await self.session.scalar(select(SourceConnection).where(SourceConnection.id == source_id))

    async def get_by_slug(self, slug: str) -> SourceConnection | None:
        return await self.session.scalar(select(SourceConnection).where(SourceConnection.slug == slug))

    async def list_all(self) -> list[SourceConnection]:
        rows = await self.session.scalars(select(SourceConnection).order_by(desc(SourceConnection.created_at)))
        return list(rows.all())

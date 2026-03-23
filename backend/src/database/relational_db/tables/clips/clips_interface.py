from __future__ import annotations

from uuid import UUID
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .clips_table import Clip, ClipAlias


class ClipsInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, clip: Clip) -> Clip:
        self.session.add(clip)
        return clip

    async def get_by_id(self, clip_id: UUID | str) -> Clip | None:
        stmt = select(Clip).options(selectinload(Clip.aliases)).where(Clip.id == clip_id)
        return await self.session.scalar(stmt)

    async def get_by_slug(self, slug: str) -> Clip | None:
        stmt = select(Clip).options(selectinload(Clip.aliases)).where(Clip.slug == slug)
        return await self.session.scalar(stmt)

    async def list_public(
        self,
        *,
        search: str | None = None,
        limit: int = 20,
    ) -> list[Clip]:
        stmt = (
            select(Clip)
            .options(selectinload(Clip.aliases))
            .where(Clip.status == "ready", Clip.is_public.is_(True))
            .order_by(Clip.created_at.desc())
            .limit(limit)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.outerjoin(ClipAlias).where(
                or_(
                    Clip.title.ilike(pattern),
                    Clip.description.ilike(pattern),
                    ClipAlias.value.ilike(pattern),
                )
            )
        rows = await self.session.scalars(stmt)
        return list(dict.fromkeys(rows.all()))

    async def list_admin(
        self,
        *,
        search: str | None = None,
        limit: int = 50,
    ) -> list[Clip]:
        stmt = (
            select(Clip)
            .options(selectinload(Clip.aliases))
            .order_by(Clip.created_at.desc())
            .limit(limit)
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.outerjoin(ClipAlias).where(
                or_(
                    Clip.title.ilike(pattern),
                    Clip.description.ilike(pattern),
                    ClipAlias.value.ilike(pattern),
                )
            )
        rows = await self.session.scalars(stmt)
        return list(dict.fromkeys(rows.all()))

    async def search_inline(self, query: str | None, limit: int = 10) -> list[Clip]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return await self.list_public(limit=limit)

        pattern = f"%{normalized_query}%"
        stmt = (
            select(Clip)
            .options(selectinload(Clip.aliases))
            .outerjoin(ClipAlias)
            .where(
                Clip.status == "ready",
                Clip.is_public.is_(True),
                or_(
                    Clip.title.ilike(pattern),
                    Clip.description.ilike(pattern),
                    ClipAlias.value.ilike(pattern),
                ),
            )
            .order_by(Clip.created_at.desc())
            .limit(limit)
        )
        rows = await self.session.scalars(stmt)
        return list(dict.fromkeys(rows.all()))

    async def replace_aliases(self, clip: Clip, aliases: list[str]) -> None:
        await self.session.execute(delete(ClipAlias).where(ClipAlias.clip_id == clip.id))
        normalized = [alias.strip() for alias in aliases if alias.strip()]
        self.session.add_all([ClipAlias(clip_id=clip.id, value=value) for value in normalized])

    async def mark_stale_uploads_failed(self, *, older_than_minutes: int = 30) -> int:
        threshold = datetime.now(UTC) - timedelta(minutes=older_than_minutes)
        result = await self.session.execute(
            update(Clip)
            .where(Clip.status.in_(("uploading", "processing")), Clip.created_at < threshold)
            .values(status="failed")
        )
        return int(result.rowcount or 0)

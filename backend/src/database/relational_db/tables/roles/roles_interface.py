from typing import Iterable, Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .roles_table import Role


class RolesInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_roles(
        self,
        *,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[Role]:
        stmt = select(Role).order_by(Role.slug)

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(or_(Role.slug.ilike(pattern), Role.name.ilike(pattern)))

        if limit:
            stmt = stmt.limit(limit)

        rows = await self.session.scalars(stmt)
        return list(rows)

    async def get_by_slug(self, slug: str) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.slug == slug)
        )
        return await self.session.scalar(stmt)

    async def get_by_slugs(self, slugs: Iterable[str]) -> list[Role]:
        slugs = list(dict.fromkeys(slugs))
        if not slugs:
            return []

        stmt = (
            select(Role)
            .where(Role.slug.in_(slugs))
        )
        rows = await self.session.scalars(stmt)
        fetched = list(rows)
        slug_to_role = {role.slug: role for role in fetched}
        return [slug_to_role[slug] for slug in slugs if slug in slug_to_role]


# class PermissionsInterface:
#     def __init__(self, session: AsyncSession):
#         self.session = session

#     async def list_permissions(
#         self,
#         *,
#         search: str | None = None,
#         limit: int | None = None,
#     ) -> list[Permission]:
#         stmt = select(Permission).order_by(Permission.slug)

#         if search:
#             pattern = f"%{search}%"
#             stmt = stmt.where(
#                 or_(Permission.slug.ilike(pattern), Permission.name.ilike(pattern))
#             )

#         if limit:
#             stmt = stmt.limit(limit)

#         rows = await self.session.scalars(stmt)
#         return list(rows)

#     async def get_by_slugs(self, slugs: Sequence[str]) -> list[Permission]:
#         if not slugs:
#             return []

#         stmt = select(Permission).where(Permission.slug.in_(slugs))
#         rows = await self.session.scalars(stmt)
#         return list(rows)

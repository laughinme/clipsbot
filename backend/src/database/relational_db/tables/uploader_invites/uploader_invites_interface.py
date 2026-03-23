from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .uploader_invites_table import UploaderInvite


class UploaderInviteInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, invite: UploaderInvite) -> UploaderInvite:
        self.session.add(invite)
        return invite

    async def get_by_id(self, invite_id: UUID | str) -> UploaderInvite | None:
        stmt = select(UploaderInvite).where(UploaderInvite.id == invite_id)
        return await self.session.scalar(stmt)

    async def get_by_token(self, token: str) -> UploaderInvite | None:
        stmt = select(UploaderInvite).where(UploaderInvite.token == token)
        return await self.session.scalar(stmt)

    async def list_recent(self, *, limit: int = 20) -> list[UploaderInvite]:
        stmt = (
            select(UploaderInvite)
            .where(
                or_(
                    UploaderInvite.status.in_(("pending", "expired")),
                    UploaderInvite.consumed_at.is_not(None),
                    UploaderInvite.revoked_at.is_not(None),
                )
            )
            .order_by(UploaderInvite.created_at.desc())
            .limit(limit)
        )
        rows = await self.session.scalars(stmt)
        return list(rows)

    async def expire_pending(self) -> int:
        stmt = select(UploaderInvite).where(
            UploaderInvite.status == "pending",
            UploaderInvite.expires_at <= datetime.now(UTC),
        )
        rows = list(await self.session.scalars(stmt))
        for invite in rows:
            invite.status = "expired"
        await self.session.flush()
        return len(rows)

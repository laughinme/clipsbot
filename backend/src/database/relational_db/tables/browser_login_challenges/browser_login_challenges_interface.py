from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .browser_login_challenges_table import BrowserLoginChallenge


class BrowserLoginChallengeInterface:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, challenge: BrowserLoginChallenge) -> BrowserLoginChallenge:
        self.session.add(challenge)
        return challenge

    async def get_by_token(self, token: str) -> BrowserLoginChallenge | None:
        stmt = select(BrowserLoginChallenge).where(BrowserLoginChallenge.token == token)
        return await self.session.scalar(stmt)

    async def count_pending_for_user(self, telegram_id: int) -> int:
        stmt = (
            select(BrowserLoginChallenge)
            .where(
                BrowserLoginChallenge.status == "approved",
                BrowserLoginChallenge.telegram_user_payload["id"].as_integer() == telegram_id,
                BrowserLoginChallenge.expires_at > datetime.now(UTC),
            )
        )
        rows = await self.session.scalars(stmt)
        return len(list(rows))
